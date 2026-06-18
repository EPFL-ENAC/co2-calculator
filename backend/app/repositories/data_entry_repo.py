"""Data entry repository for database operations."""

import asyncio
from typing import Any, Dict, Optional

from psycopg.types.json import Json
from pydantic import BaseModel
from sqlalchemy import Select, asc, desc, func, or_
from sqlalchemy import select as sa_select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import aliased
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.building_room import BuildingRoom
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.location import Location, TransportModeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.modules.professional_travel.schemas import MemberEntry
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.schemas.carbon_report_response import SubmoduleResponse, SubmoduleSummary
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryUpdate,
    ModuleHandler,
)
from app.utils.data_entry_emission_type_map import (
    DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION,
    ROLLUP_EMISSION_TYPE_IDS,
)

logger = get_logger(__name__)

# Default filter map when handler doesn't provide one
DEFAULT_FILTER_MAP = {"name": DataEntry.data["name"].as_string()}

# COPY target for ``bulk_copy`` — every non-defaulted data_entries column.
# ``id`` is omitted so the sequence assigns it server-side.
_DATA_ENTRY_COPY_SQL = """
COPY data_entries (
    data_entry_type_id, carbon_report_module_id, data, status,
    source, created_by_id, created_at, updated_at, year, unit_id
) FROM STDIN
"""


class DataEntryRepository:
    """Repository for data entry database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.entity_type = DataEntry.__name__
        self.carbon_report_module_repo = CarbonReportModuleRepository(session)

    def _detach(self, *objs: Any) -> None:
        """Expunge ORM rows from the session so accidental mutations cannot
        be flushed back to the DB. Use on read-path methods that return rows
        the caller should treat as read-only.

        Silently ignores rows that are not currently attached.
        """
        for obj in objs:
            if obj is None:
                continue
            try:
                self.session.expunge(obj)
            except InvalidRequestError:
                # Already detached or session-state edge case — nothing to do.
                pass

    async def get(self, id: int) -> Optional[DataEntry]:
        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.exec(statement)
        return result.one_or_none()

    async def create(self, data: DataEntry) -> DataEntry:
        # 1. Convert Input Model to Table Model

        db_obj = DataEntry.model_validate({**data.dict()})

        # 3. Save
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def bulk_create(self, data_entries: list[DataEntry]) -> list[DataEntry]:
        """Bulk create data entries."""
        db_objs = [DataEntry.model_validate(entry) for entry in data_entries]
        self.session.add_all(db_objs)
        await self.session.flush()
        return db_objs

    async def bulk_copy(self, data_entries: list[DataEntry]) -> int:
        """Bulk insert via PostgreSQL ``COPY … FROM STDIN`` (psycopg3).

        Runs on the session's own connection, so the COPY participates in
        the session's open transaction — a later rollback discards it.
        Unlike ``bulk_create`` it never returns ORM objects and ids are
        NOT populated; callers that need ids (audit trail, immediate
        emission build) must use ``bulk_create``.

        On non-PostgreSQL binds (the SQLite test harness) COPY is not part
        of the wire protocol, so the ORM bulk path is used instead.
        """
        # Validate in chunks, yielding between them: a full batch can be
        # INGEST_COPY_BATCH_SIZE (50k) rows, and one un-yielded model_validate
        # list-comp blocks the event loop long enough to fail liveness probes.
        db_objs: list[DataEntry] = []
        for i, entry in enumerate(data_entries):
            db_objs.append(DataEntry.model_validate(entry))
            if (i + 1) % 1000 == 0:
                await asyncio.sleep(0)
        if not db_objs:
            return 0
        bind = self.session.get_bind()
        if bind.dialect.driver != "psycopg":
            # COPY streaming here is psycopg3-specific (``cursor().copy()``).
            # Production runs ``postgresql+psycopg``; SQLite and the
            # asyncpg-based test fixtures take the ORM path.
            logger.info(
                f"bulk_copy: non-psycopg driver ({bind.dialect.driver}) — "
                f"using ORM bulk insert for {len(db_objs)} entries"
            )
            self.session.add_all(db_objs)
            await self.session.flush()
            return len(db_objs)

        sa_conn = await self.session.connection()
        raw = await sa_conn.get_raw_connection()
        driver_conn = raw.driver_connection  # psycopg AsyncConnection
        if driver_conn is None:
            raise RuntimeError("bulk_copy: raw connection has no driver connection")
        async with driver_conn.cursor() as cur:
            async with cur.copy(_DATA_ENTRY_COPY_SQL) as copy:
                for obj in db_objs:
                    await copy.write_row(
                        (
                            obj.data_entry_type_id,
                            obj.carbon_report_module_id,
                            Json(obj.data or {}),
                            # Native PG enum column stores the member name.
                            obj.status.name if obj.status is not None else None,
                            obj.source,
                            obj.created_by_id,
                            obj.created_at,
                            obj.updated_at,
                            obj.year,
                            obj.unit_id,
                        )
                    )
        return len(db_objs)

    async def bulk_delete(
        self, carbon_report_module_id: int, data_entry_type_id: DataEntryTypeEnum
    ) -> None:
        """Bulk delete data entries by module and type."""
        statement = delete(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
            col(DataEntry.data_entry_type_id) == data_entry_type_id,
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def bulk_delete_by_source(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: DataEntryTypeEnum,
        source: int,  # DataEntrySourceEnum value
    ) -> None:
        """
        Bulk delete data entries by module, type, and source.

        Args:
            carbon_report_module_id: The module to delete from
            data_entry_type_id: The data entry type to delete
            source: Only delete entries from this source (e.g., CSV_MODULE_PER_YEAR)
        """
        statement = delete(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
            col(DataEntry.data_entry_type_id) == data_entry_type_id.value,
            col(DataEntry.source) == source,
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def bulk_delete_by_source_year(
        self,
        year: int,
        data_entry_type_ids: list[int],
        source: int,  # DataEntrySourceEnum value
    ) -> int:
        """Full-year replace delete for MODULE_PER_YEAR ingest.

        Per-year CSVs are complete exports: a new upload replaces ALL
        prior rows of that (year, type, source) regardless of unit, so
        the delete keys on the denormalized ``data_entries.year`` column
        — no module-tree resolution, one indexed statement.  Returns
        the number of rows deleted.
        """
        if not data_entry_type_ids:
            return 0
        statement = delete(DataEntry).where(
            col(DataEntry.year) == year,
            col(DataEntry.data_entry_type_id).in_(data_entry_type_ids),
            col(DataEntry.source) == source,
        )
        result = await self.session.execute(statement)
        await self.session.flush()
        return getattr(result, "rowcount", 0) or 0

    async def update(
        self, id: int, data: DataEntryUpdate, user_id: int
    ) -> Optional[DataEntry]:
        # POTENTIAL OPTIMIZATION: Use SQLAlchemy's update() for direct updates
        # 1. Fetch the existing record

        statement = select(DataEntry).where(DataEntry.id == id)
        result = await self.session.exec(statement)
        db_obj = result.one_or_none()

        if not db_obj:
            return None

        # 2. Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "data" and value is not None:
                # Merge dicts instead of replacing
                db_obj.data = {**db_obj.data, **value}
            else:
                setattr(db_obj, field, value)

        # 4. Save
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def delete(self, id: int) -> bool:
        statement = delete(DataEntry).where(col(DataEntry.id) == id)
        result = await self.session.execute(statement)

        # rowcount tells you if a row actually matched the ID
        deleted = result.rowcount if hasattr(result, "rowcount") else None

        await self.session.flush()
        return bool(deleted)

    async def check_json_field_unique(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        field: str,
        value: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """Check whether a JSON data field value is unique within a submodule.

        Args:
            carbon_report_module_id: The module to scope the check to.
            data_entry_type_id: The submodule type.
            field: The JSON key inside ``DataEntry.data`` to check.
            value: The value that must be unique.
            exclude_id: Optional entry ID to exclude (for PATCH uniqueness checks).

        Returns:
            True if the value is unique (no conflicting row found), False otherwise.
        """
        statement = (
            select(DataEntry)
            .where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                col(DataEntry.data_entry_type_id) == data_entry_type_id,
                DataEntry.data[field].as_string() == value,
            )
            .limit(1)
        )
        if exclude_id is not None:
            statement = statement.where(col(DataEntry.id) != exclude_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is None

    async def get_list(
        self,
        carbon_report_module_id: int,
        # unit_id,
        # year,
        limit,
        offset,
        sort_by,
        sort_order,
        filter: Optional[str] = None,
    ) -> list[DataEntry]:
        # TODO: check if it's safe to expunge the returned rows here for
        # symmetry with get_submodule_data. Some callers (delete flows in
        # data_entry_service.py) only read; others may mutate. Audit each
        # caller before adding self._detach.
        statement = select(DataEntry).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id
        )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(DataEntry, sort_by).asc())
        else:
            statement = statement.order_by(getattr(DataEntry, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_by_data_entry_type_and_year(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
        carbon_report_module_ids: Optional[list[int]] = None,
    ) -> list[DataEntry]:
        """Fetch all DataEntries for a given data_entry_type and report year.

        JOINs DataEntry → CarbonReportModule → CarbonReport to filter by year.

        Args:
            data_entry_type_id: The data entry type to filter on.
            year: The carbon report year to filter on.
            carbon_report_module_ids: Optional module scope — set by
                unit-specific ingests so their recalc touches only the
                uploaded module instead of the whole (det, year) slice.

        Returns:
            List of matching DataEntry rows (may be empty).
        """
        # TODO: check if it's safe to expunge the returned rows here for
        # symmetry with get_submodule_data. The recalculation workflow in
        # workflows/emission_recalculation.py is the primary caller and may
        # mutate; audit before adding self._detach.
        statement = (
            select(DataEntry)
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                col(DataEntry.data_entry_type_id) == data_entry_type_id,
                col(CarbonReport.year) == year,
            )
        )
        if carbon_report_module_ids:
            statement = statement.where(
                col(DataEntry.carbon_report_module_id).in_(carbon_report_module_ids)
            )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_module_type_id_for_carbon_report_module(
        self, carbon_report_module_id: int
    ) -> Optional[int]:
        return await self.carbon_report_module_repo.get_module_type(
            carbon_report_module_id
        )

    async def get_total_count_by_submodule(
        self,
        carbon_report_module_id: int,
        travel_institutional_id_filter: Optional[str] = None,
    ) -> Dict[int, int]:
        """
        Docstring for get_total_count_by_submodule

        :param self: Description
        :param carbon_report_module_id: Description
        :type carbon_report_module_id: int
        :return: Description
        :rtype: Dict[int, int]

        Dict mapping submodule (data_entry_type_id) to total item count:
            {
                1: 10,
                2: 5,
                ...
            }
        """
        # Determine module_type_id from carbon_report_module_id

        module_type_id = await self.get_module_type_id_for_carbon_report_module(
            carbon_report_module_id
        )
        if module_type_id is None:
            return {}

        all_type_ids = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(
            ModuleTypeEnum(module_type_id), []
        )

        # Get actual counts from DB
        query: Select = (
            select(
                DataEntry.data_entry_type_id,
                func.count().label("total_count"),
            )
            .where(DataEntry.carbon_report_module_id == carbon_report_module_id)
            .group_by(col(DataEntry.data_entry_type_id))
        )
        if travel_institutional_id_filter is not None:
            travel_type_ids = (
                DataEntryTypeEnum.plane.value,
                DataEntryTypeEnum.train.value,
            )
            query = query.where(
                or_(
                    col(DataEntry.data_entry_type_id).not_in(travel_type_ids),
                    DataEntry.data["user_institutional_id"].as_string()
                    == travel_institutional_id_filter,
                )
            )
        result = await self.session.execute(query)
        rows = list(result.all())
        aggregation: Dict[int, int] = {
            data_entry_type_id: int(total_count)
            for data_entry_type_id, total_count in rows
        }

        # Fill in zeros for missing types
        for type_id in all_type_ids:
            if type_id not in aggregation:
                aggregation[type_id] = 0

        return aggregation

    def _apply_name_filter(
        self, statement, filter: Optional[str], handler: ModuleHandler
    ):
        """
        Applies a filter to the given SQLAlchemy statement based on
        the handler's filter_map if a valid filter is provided.
        """
        filter_pattern = ""
        if filter:
            filter = filter.strip()
            # max filter for security
            if len(filter) > 100:
                filter = filter[:100]
            # check for empty or only-wildcard filters and handle accordingly.
            if filter == "" or filter == "%" or filter == "*":
                filter = None

        if filter:
            filter_pattern = f"%{filter}%"
            # Get filter map from handler, default to filtering by name
            filter_map = getattr(handler, "filter_map", {}) or DEFAULT_FILTER_MAP

            # Build OR conditions for all filter fields
            conditions = [
                filter_expr.ilike(filter_pattern) for filter_expr in filter_map.values()
            ]
            statement = statement.where(or_(*conditions))
        return statement, filter_pattern

    def _apply_sort(self, statement, sort_by: str, sort_order: str, sort_map: dict):
        sort_expr = sort_map.get(sort_by)
        if sort_expr is None:
            raise ValueError(f"Cannot sort by unknown field: {sort_by}")
        if sort_order.lower() == "asc":
            return statement.order_by(asc(sort_expr))
        else:
            return statement.order_by(desc(sort_expr))

    async def get_submodule_data(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
        filter: Optional[str] = None,
        institutional_id_filter: Optional[str] = None,
    ) -> SubmoduleResponse:
        is_travel_entry = data_entry_type_id in (
            DataEntryTypeEnum.plane.value,
            DataEntryTypeEnum.train.value,
        )
        is_train_entry = data_entry_type_id == DataEntryTypeEnum.train.value
        is_plane_entry = data_entry_type_id == DataEntryTypeEnum.plane.value
        OriginLocation: Any = None
        DestLocation: Any = None
        is_buildings_entry = data_entry_type_id in (DataEntryTypeEnum.building.value,)
        is_headcount_entry = data_entry_type_id in (
            DataEntryTypeEnum.member.value,
            DataEntryTypeEnum.student.value,
        )

        if is_buildings_entry:
            # --- Direct JOIN on rollup row (avoids GROUP BY, prevents double-count) ---
            # The rollup row (emission_type_id == buildings__rooms) stores the
            # pre-aggregated total for each building data_entry, written by
            # DataEntryEmissionService.prepare_create().
            rollup_et_id = DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION[
                DataEntryTypeEnum.building
            ].value
            RollupEmission = aliased(DataEntryEmission)
            # Fallback for legacy rows created before rollups existed.
            building_emission_agg_q = select(
                DataEntryEmission.data_entry_id,
                func.sum(DataEntryEmission.kg_co2eq).label("total_kg_co2eq"),
            ).group_by(col(DataEntryEmission.data_entry_id))
            if ROLLUP_EMISSION_TYPE_IDS:
                building_emission_agg_q = building_emission_agg_q.where(
                    col(DataEntryEmission.emission_type_id).notin_(
                        ROLLUP_EMISSION_TYPE_IDS
                    )
                )
            building_emission_agg = building_emission_agg_q.subquery()
            building_total_kg_expr: Any = func.coalesce(
                col(RollupEmission.kg_co2eq),
                building_emission_agg.c.total_kg_co2eq,
            )
            entities: list[Any] = [
                DataEntry,
                building_total_kg_expr.label("total_kg_co2eq"),
                Factor,
                BuildingRoom,
            ]
            statement: Select[Any] = (
                sa_select(*entities)
                .join(
                    RollupEmission,
                    (col(RollupEmission.data_entry_id) == col(DataEntry.id))
                    & (col(RollupEmission.emission_type_id) == rollup_et_id)
                    & (col(RollupEmission.scope).is_(None)),
                    isouter=True,
                )
                .join(
                    Factor,
                    col(RollupEmission.primary_factor_id) == col(Factor.id),
                    isouter=True,
                )
                .join(
                    BuildingRoom,
                    DataEntry.data["room_name"].as_string()
                    == col(BuildingRoom.room_name),
                    isouter=True,
                )
                .join(
                    building_emission_agg,
                    col(building_emission_agg.c.data_entry_id) == col(DataEntry.id),
                    isouter=True,
                )
            )
            kg_sort_expr = building_total_kg_expr
        elif is_headcount_entry:
            # --- Direct JOIN on rollup row (avoids GROUP BY, prevents double-count) ---
            # Headcount entries (member/student) produce multiple leaf emissions
            # (food, waste, commuting). We persist a single scope=NULL rollup row
            # per entry so the table can sort by total kg_co2eq via a simple JOIN.
            rollup_et_id = DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION[
                DataEntryTypeEnum(data_entry_type_id)
            ].value
            RollupEmission = aliased(DataEntryEmission)
            entities = [
                DataEntry,
                RollupEmission.kg_co2eq.label("total_kg_co2eq"),  # type: ignore[attr-defined]
                Factor,
            ]
            statement = (
                sa_select(*entities)
                .join(
                    RollupEmission,
                    (col(RollupEmission.data_entry_id) == col(DataEntry.id))
                    & (col(RollupEmission.emission_type_id) == rollup_et_id)
                    & (col(RollupEmission.scope).is_(None)),
                    isouter=True,
                )
                .join(
                    Factor,
                    col(RollupEmission.primary_factor_id) == col(Factor.id),
                    isouter=True,
                )
            )
            kg_sort_expr = RollupEmission.kg_co2eq
        else:
            # --- Aggregation subquery for multi-emission entries ---
            # Exclude rollup rows so future rollup types are never double-counted.
            emission_agg_q = select(
                DataEntryEmission.data_entry_id,
                func.sum(DataEntryEmission.kg_co2eq).label("total_kg_co2eq"),
                func.min(DataEntryEmission.primary_factor_id).label(
                    "primary_factor_id"
                ),
            ).group_by(col(DataEntryEmission.data_entry_id))
            if ROLLUP_EMISSION_TYPE_IDS:
                emission_agg_q = emission_agg_q.where(
                    col(DataEntryEmission.emission_type_id).notin_(
                        ROLLUP_EMISSION_TYPE_IDS
                    )
                )
            emission_agg = emission_agg_q.subquery()

            entities = [DataEntry, emission_agg.c.total_kg_co2eq, Factor]
            if is_travel_entry:
                entities.extend([MemberEntry, DataEntryEmission])
                if is_train_entry or is_plane_entry:
                    OriginLocation = aliased(Location)
                    DestLocation = aliased(Location)
                    entities.extend([OriginLocation, DestLocation])
            statement = (
                sa_select(*entities)
                .join(
                    emission_agg,
                    col(DataEntry.id) == emission_agg.c.data_entry_id,
                    isouter=True,
                )
                .join(
                    Factor,
                    emission_agg.c.primary_factor_id == col(Factor.id),
                    isouter=True,
                )
            )

            if is_travel_entry:
                statement = statement.join(
                    MemberEntry,
                    (
                        MemberEntry.data["user_institutional_id"].as_string()
                        == DataEntry.data["user_institutional_id"].as_string()
                    )
                    & (
                        col(MemberEntry.carbon_report_module_id)
                        == col(DataEntry.carbon_report_module_id)
                    )
                    & (
                        col(MemberEntry.data_entry_type_id)
                        == DataEntryTypeEnum.member.value
                    ),
                    isouter=True,
                ).join(
                    DataEntryEmission,
                    col(DataEntryEmission.data_entry_id) == DataEntry.id,
                    isouter=True,
                )
                if is_train_entry:
                    statement = statement.join(
                        OriginLocation,
                        (
                            OriginLocation.name
                            == DataEntry.data["origin_name"].as_string()
                        )
                        & (
                            col(OriginLocation.transport_mode)
                            == TransportModeEnum.train
                        ),
                        isouter=True,
                    ).join(
                        DestLocation,
                        (
                            DestLocation.name
                            == DataEntry.data["destination_name"].as_string()
                        )
                        & (col(DestLocation.transport_mode) == TransportModeEnum.train),
                        isouter=True,
                    )
                elif is_plane_entry:
                    statement = statement.join(
                        OriginLocation,
                        (
                            OriginLocation.iata_code
                            == DataEntry.data["origin_iata"].as_string()
                        )
                        & (
                            col(OriginLocation.transport_mode)
                            == TransportModeEnum.plane
                        ),
                        isouter=True,
                    ).join(
                        DestLocation,
                        (
                            DestLocation.iata_code
                            == DataEntry.data["destination_iata"].as_string()
                        )
                        & (col(DestLocation.transport_mode) == TransportModeEnum.plane),
                        isouter=True,
                    )
            kg_sort_expr = emission_agg.c.total_kg_co2eq

        statement = statement.where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
            col(DataEntry.data_entry_type_id) == data_entry_type_id,
        )

        if institutional_id_filter is not None and is_travel_entry:
            statement = statement.where(
                DataEntry.data["user_institutional_id"].as_string()
                == institutional_id_filter
            )

        handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum(data_entry_type_id))
        handler_default = getattr(handler, "default_where", [])
        if handler_default:
            statement = statement.where(*handler_default)
        statement, filter_pattern = self._apply_name_filter(statement, filter, handler)

        sort_map = dict(
            handler.sort_map
        )  # shallow copy — don't mutate the class-level dict
        sort_map["kg_co2eq"] = kg_sort_expr
        if is_travel_entry:
            sort_map["distance_km"] = func.coalesce(
                DataEntryEmission.additional_value,
                DataEntry.data["distance_km"].as_float(),
            )
        if (is_train_entry or is_plane_entry) and OriginLocation is not None:
            sort_map["origin_name"] = OriginLocation.name
            sort_map["destination_name"] = DestLocation.name
        statement = self._apply_sort(statement, sort_by, sort_order, sort_map)

        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)

        # Query for total count (for pagination)
        count_stmt = select(func.count()).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id,
            DataEntry.data_entry_type_id == data_entry_type_id,
        )
        if institutional_id_filter is not None and is_travel_entry:
            count_stmt = count_stmt.where(
                DataEntry.data["user_institutional_id"].as_string()
                == institutional_id_filter
            )
        if handler_default:
            count_stmt = count_stmt.where(*handler_default)
        if filter_pattern != "":
            # Get filter map from handler, default to filtering by name
            filter_map = getattr(handler, "filter_map", {}) or DEFAULT_FILTER_MAP

            # Build OR conditions for all filter fields
            conditions = [
                filter_expr.ilike(filter_pattern) for filter_expr in filter_map.values()
            ]
            count_stmt = count_stmt.where(or_(*conditions))
        total_items = (await self.session.execute(count_stmt)).scalar_one()
        rows = result.all()
        count = len(rows)

        items: list[BaseModel] = []

        for row in rows:
            # Pre-bind conditionally-unpacked variables so static type checkers
            # see them as definitely-bound (T | None) on every branch path.
            # MemberEntry is a SQLAlchemy alias of DataEntry, so the runtime
            # type is DataEntry.
            member_entry: DataEntry | None = None
            _emission: DataEntryEmission | None = None
            building_room: BuildingRoom | None = None
            _origin_loc: Location | None = None
            _dest_loc: Location | None = None
            # Unpack based on query shape
            # 1. Extract the common base fields right away
            data_entry, total_kg_co2eq, primary_factor = row[:3]

            # 2. Unpack only the remaining tail fields
            if is_travel_entry:
                if is_train_entry or is_plane_entry:
                    member_entry, _emission, _origin_loc, _dest_loc = row[3:]
                else:
                    member_entry, _emission = row[3:]
            elif is_buildings_entry:
                building_room = row[3]

            # Defense-in-depth: detach loaded ORM rows from the session so any
            # accidental mutation (here or downstream) cannot be flushed back to
            # the DB. This method only reads scalar columns and the JSON `data`
            # field after unpack — no lazy relationships — so expunge is safe.
            self._detach(data_entry, primary_factor)
            if is_travel_entry:
                self._detach(member_entry, _emission, _origin_loc, _dest_loc)
            elif is_buildings_entry:
                self._detach(building_room)

            handler = BaseModuleHandler.get_by_type(
                DataEntryTypeEnum(data_entry.data_entry_type_id)
            )
            # If primary_factor is None, try to fetch it
            # from DataEntry.data["primary_factor_id"]
            if primary_factor is None:
                primary_factor_id = data_entry.data.get("primary_factor_id")
                if primary_factor_id:
                    factor_stmt = select(Factor).where(Factor.id == primary_factor_id)
                    factor_result = await self.session.execute(factor_stmt)
                    primary_factor = factor_result.scalar_one_or_none()
                    if primary_factor is not None:
                        self._detach(primary_factor)

            primary_factor_values = primary_factor.values if primary_factor else {}
            primary_factor_classification = (
                primary_factor.classification if primary_factor else {}
            )
            # Build the enriched response payload as a fresh dict — never
            # mutate `data_entry.data`, which would dirty the ORM row and
            # cause SQLAlchemy to flush computed values back into the source-
            # of-truth JSON column on the next session flush/commit.
            enriched_data: dict = {
                **data_entry.data,
                "kg_co2eq": total_kg_co2eq,
                "primary_factor": {
                    **primary_factor_values,
                    **primary_factor_classification,
                },
            }

            if is_travel_entry:
                distance_km = (
                    float(_emission.additional_value)
                    if _emission is not None and _emission.additional_value is not None
                    else enriched_data.get("distance_km")
                )
                if member_entry is not None:
                    enriched_data["traveler_name"] = member_entry.data.get("name")
                if distance_km is not None:
                    enriched_data["distance_km"] = distance_km
                if is_train_entry or is_plane_entry:
                    if _origin_loc is not None:
                        enriched_data["origin_name"] = _origin_loc.name
                    if _dest_loc is not None:
                        enriched_data["destination_name"] = _dest_loc.name
            if is_buildings_entry and building_room:
                enriched_data["room_surface_square_meter"] = (
                    building_room.room_surface_square_meter
                )

            items.append(handler.to_response(data_entry, enriched_data))

        response = SubmoduleResponse(
            id=data_entry_type_id,
            count=count,
            items=items,
            summary=SubmoduleSummary(
                total_items=total_items,
                annual_consumption_kwh=0.0,
                total_kg_co2eq=0.0,
                annual_fte=0.0,
            ),
            has_more=total_items > offset + count,
        )
        return response

    async def get_professional_travel_trip_legs(
        self,
        carbon_report_module_id: int,
        institutional_id_filter: Optional[str] = None,
        max_rows: int = 10000,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch raw plane + train legs (one row per DataEntry, no GROUP BY)
        with origin/destination coordinates; the client aggregates and sums
        ``number_of_trips``. Rows whose origin or destination location did not
        resolve are dropped and counted into the returned ``dropped`` total.
        """
        # Scope the per-entry emission rollup to THIS module's entries. Without
        # it, the subquery seq-scans and aggregates the whole emissions table
        # (~700k rows) on every call — and the mode loop below runs it twice —
        # which dominates the query (seconds on a cold cache). Restricting by
        # data_entry_id turns that into an indexed lookup of the module's rows.
        module_entry_ids = select(col(DataEntry.id)).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id
        )
        emission_agg_q = (
            select(
                DataEntryEmission.data_entry_id,
                func.sum(DataEntryEmission.kg_co2eq).label("total_kg_co2eq"),
            )
            .where(col(DataEntryEmission.data_entry_id).in_(module_entry_ids))
            .group_by(col(DataEntryEmission.data_entry_id))
        )
        if ROLLUP_EMISSION_TYPE_IDS:
            emission_agg_q = emission_agg_q.where(
                col(DataEntryEmission.emission_type_id).notin_(ROLLUP_EMISSION_TYPE_IDS)
            )
        emission_agg = emission_agg_q.subquery()

        legs: list[dict[str, Any]] = []
        dropped = 0

        # Resolve both modes through the unique Location.natural_key. Plane
        # entries store an IATA code, so derive "plane:<iata>" to match
        # Location.compute_natural_key; train entries already carry the key
        # (names alone collide, e.g. "Berne" → Bern CH + two DE stops).
        for mode, type_enum, origin_key, dest_key in (
            (
                "plane",
                DataEntryTypeEnum.plane,
                "plane:" + DataEntry.data["origin_iata"].as_string(),
                "plane:" + DataEntry.data["destination_iata"].as_string(),
            ),
            (
                "train",
                DataEntryTypeEnum.train,
                DataEntry.data["origin_natural_key"].as_string(),
                DataEntry.data["destination_natural_key"].as_string(),
            ),
        ):
            OriginLocation = aliased(Location)
            DestLocation = aliased(Location)
            # Traveler identity (SCIPER) stored on the entry. The display name is
            # resolved later from the unit's headcount roster (the canonical
            # source), not the User table — see ``get_professional_travel_trips_map``.
            traveler_id_key = DataEntry.data["user_institutional_id"].as_string()

            select_entities: list[Any] = [
                OriginLocation.latitude,
                OriginLocation.longitude,
                OriginLocation.name,
                DestLocation.latitude,
                DestLocation.longitude,
                DestLocation.name,
                emission_agg.c.total_kg_co2eq,
                DataEntry.data["number_of_trips"].as_float(),
                traveler_id_key,
            ]
            statement: Select[Any] = (
                sa_select(*select_entities)
                .select_from(DataEntry)
                .join(
                    emission_agg,
                    col(DataEntry.id) == emission_agg.c.data_entry_id,
                    isouter=True,
                )
                .join(
                    OriginLocation,
                    OriginLocation.natural_key == origin_key,
                    isouter=True,
                )
                .join(
                    DestLocation,
                    DestLocation.natural_key == dest_key,
                    isouter=True,
                )
            )

            statement = statement.where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                col(DataEntry.data_entry_type_id) == type_enum.value,
            )
            if institutional_id_filter is not None:
                statement = statement.where(
                    DataEntry.data["user_institutional_id"].as_string()
                    == institutional_id_filter
                )

            # max_rows is a global cap across both modes, so bound the second
            # query by what the first already consumed (returned + dropped).
            remaining = max_rows - (len(legs) + dropped)
            if remaining <= 0:
                break
            statement = statement.limit(remaining)
            result = await self.session.execute(statement)
            for row in result.all():
                (
                    o_lat,
                    o_lng,
                    o_name,
                    d_lat,
                    d_lng,
                    d_name,
                    kg,
                    n_trips,
                    traveler_id,
                ) = row
                if o_lat is None or o_lng is None or d_lat is None or d_lng is None:
                    dropped += 1
                    continue
                tid = traveler_id or ""
                legs.append(
                    {
                        "mode": mode,
                        "origin_lat": float(o_lat),
                        "origin_lng": float(o_lng),
                        "destination_lat": float(d_lat),
                        "destination_lng": float(d_lng),
                        "origin_name": o_name or "",
                        "destination_name": d_name or "",
                        "kg_co2eq": float(kg or 0.0),
                        "number_of_trips": int(n_trips) if n_trips is not None else 1,
                        "traveler_id": tid,
                        # traveler_name is filled from the headcount roster in the
                        # service; default to the SCIPER until then.
                        "traveler_name": tid,
                    }
                )

        if len(legs) + dropped >= max_rows:
            logger.warning(
                "trips-map row cap hit",
                extra={
                    "carbon_report_module_id": carbon_report_module_id,
                    "max_rows": max_rows,
                    "returned": len(legs),
                    "dropped": dropped,
                },
            )

        return legs, dropped

    async def get_total_per_field(
        self,
        field_name: str,
        carbon_report_module_id: int,
        data_entry_type_id: Optional[int] = None,
    ) -> float:
        """Get total sum for a specific field across data entries.

        :param field_name: The field to sum (e.g., 'fte', 'kg_co2eq').
        :param carbon_report_module_id: The carbon report module ID to filter by.
        :param data_entry_type_id: Optional data entry type ID to filter by.
        :return: The total sum as a float.
        """
        if hasattr(DataEntry, field_name):
            sum_field = getattr(DataEntry, field_name)
        else:
            sum_field = DataEntry.data[field_name].as_float()

        statement = select(func.sum(sum_field).label("total")).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id
        )
        if data_entry_type_id is not None:
            statement = statement.where(
                DataEntry.data_entry_type_id == data_entry_type_id
            )

        result = await self.session.execute(statement)
        total = result.scalar_one()
        return float(total or 0.0)

    async def get_stats(
        self,
        carbon_report_module_id,
        aggregate_by: str = "data_entry_type_id",
        aggregate_field: str = "fte",
        data_entry_type_id: Optional[int] = None,
    ) -> Dict[str, Optional[float]]:
        """Aggregate DataEntry data by submodule or function.
                SELECT
            dee.*
        FROM
            data_entry_emission dee
        JOIN
            data_entry de ON dee.data_entry_id = de.id
        WHERE
            de.carbon_report_module_id = 'YOUR_REPORT_ID_HERE';
        """
        # 1. Get the model attributes dynamically
        if hasattr(DataEntry, aggregate_by):
            group_field = getattr(DataEntry, aggregate_by)
        else:
            group_field = DataEntry.data[aggregate_by].as_string()
        if hasattr(DataEntry, aggregate_field):
            sum_field = getattr(DataEntry, aggregate_field)
        else:
            sum_field = DataEntry.data[aggregate_field].as_float()

        # 2. Build the query with the JOIN
        query = (
            select(
                group_field,
                func.sum(sum_field).label("total"),
            )
            .where(
                DataEntry.carbon_report_module_id == carbon_report_module_id,
            )
            .group_by(group_field)
        )
        if data_entry_type_id is not None:
            query = query.where(DataEntry.data_entry_type_id == data_entry_type_id)

        result = await self.session.execute(
            query
        )  # Changed .exec to .execute (Standard SQLAlchemy/SQLModel)
        rows = result.all()

        # 3. Format the results
        aggregation: Dict[str, Optional[float]] = {}
        for key, total_count in rows:
            label = str(key) if key is not None else "unknown"
            if label not in aggregation:
                aggregation[label] = None
            if total_count is not None:
                aggregation[label] = (aggregation[label] or 0.0) + total_count

        return aggregation

    async def get_stats_by_carbon_report_id(
        self,
        carbon_report_id: int,
        aggregate_by: str = "module_type_id",
        aggregate_field: str = "fte",
        *,
        validated_only: bool = True,
    ) -> Dict[str, float]:
        """Aggregate DataEntry data by module_type_id for a whole carbon report.

        Joins DataEntry → CarbonReportModule.
        Filters: carbon_report_id, module status == VALIDATED.
        Default aggregation: SUM(fte) grouped by module_type_id.

        Returns:
            {"1": 4532.0}  (headcount module FTE)
        """
        # Resolve group field
        if aggregate_by == "module_type_id":
            group_field = col(CarbonReportModule.module_type_id)
        elif hasattr(DataEntry, aggregate_by):
            group_field = getattr(DataEntry, aggregate_by)
        else:
            group_field = DataEntry.data[aggregate_by].as_string()

        # Resolve sum field
        if hasattr(DataEntry, aggregate_field):
            sum_field = getattr(DataEntry, aggregate_field)
        else:
            sum_field = DataEntry.data[aggregate_field].as_float()

        query = (
            select(
                group_field,
                func.sum(sum_field).label("total"),
            )
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(
                CarbonReportModule.carbon_report_id == carbon_report_id,
                *(
                    []
                    if not validated_only
                    else [CarbonReportModule.status == ModuleStatus.VALIDATED]
                ),
            )
            .group_by(group_field)
        )

        result = await self.session.execute(query)
        rows = result.all()

        aggregation: Dict[str, float] = {}
        for key, total in rows:
            label = str(key) if key is not None else "unknown"
            aggregation[label] = float(total) if total is not None else 0.0

        return aggregation

    async def get_headcount_members(
        self,
        carbon_report_module_id: int,
    ) -> list[dict]:
        """Return members with an institutional ID, ordered by name.

        Args:
            carbon_report_module_id: The headcount module to query.

        Returns:
            List of dicts with ``institutional_id`` and ``name`` keys.
        """
        statement = (
            select(DataEntry.data)
            .where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                col(DataEntry.data_entry_type_id) == DataEntryTypeEnum.member.value,
                DataEntry.data["user_institutional_id"].as_string().isnot(None),
            )
            .order_by(DataEntry.data["name"].as_string())
        )
        result = await self.session.execute(statement)
        rows = result.scalars().all()
        members = []
        for data in rows:
            uid = data.get("user_institutional_id")
            if uid:
                members.append({"institutional_id": uid, "name": data.get("name", "")})
        return members

    async def get_member_by_institutional_id(
        self,
        carbon_report_module_id: int,
        institutional_id: str,
    ) -> Optional[dict]:
        """Fetch the member entry whose user_institutional_id matches.

        Args:
            carbon_report_module_id: The headcount module to scope the search.
            institutional_id: The institutional ID (digits only) to look up.

        Returns:
            Dict with ``institutional_id`` and ``name`` keys, or ``None`` if not found.
        """
        statement = (
            select(DataEntry.data)
            .where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                col(DataEntry.data_entry_type_id) == DataEntryTypeEnum.member.value,
                DataEntry.data["user_institutional_id"].as_string() == institutional_id,
            )
            .limit(1)
        )
        result = await self.session.execute(statement)
        data = result.scalar_one_or_none()
        if data is None:
            return None
        uid = data.get("user_institutional_id")
        if not uid:
            return None
        return {"institutional_id": uid, "name": data.get("name", "")}
