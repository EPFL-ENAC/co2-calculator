"""Data entry repository for database operations."""

import asyncio
from typing import Any

from psycopg.types.json import Json
from pydantic import BaseModel, ValidationError
from sqlalchemy import Select, and_, asc, desc, func, or_
from sqlalchemy import select as sa_select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import aliased
from sqlmodel import col, delete, insert, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.building_room import BuildingRoom
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.location import Location, TransportModeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.modules.emissions.registry import (
    DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION,
    ROLLUP_EMISSION_TYPE_IDS,
)
from app.modules.headcount.data_entries import OTHER_SIUS_CODE
from app.modules.professional_travel import MemberEntry
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.schemas.carbon_report_response import SubmoduleResponse, SubmoduleSummary
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryUpdate,
)

logger = get_logger(__name__)


class HeadcountFteBreakdown(BaseModel):
    """The three FTE figures the headcount module page needs (#2050 J2)."""

    total_fte: float
    student_fte: float
    # None where the group exists but recorded no FTE — distinct from 0.0.
    member_fte_by_sius_code: dict[str, float | None]


# Default filter map when handler doesn't provide one
DEFAULT_FILTER_MAP = {"name": DataEntry.data["name"].as_string()}

# data_entry_type ids that make up the Equipment module (issue #259 "new vs
# previous year" detection applies only to these).
EQUIPMENT_DATA_ENTRY_TYPE_IDS = {
    DataEntryTypeEnum.scientific.value,
    DataEntryTypeEnum.it.value,
    DataEntryTypeEnum.other.value,
}

EQUIPMENT_USAGE_FIELDS = (
    "active_usage_hours_per_week",
    "standby_usage_hours_per_week",
)

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

    async def get(self, id: int) -> DataEntry | None:
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

    async def bulk_insert_returning_ids(self, rows: list[dict]) -> list[int]:
        """Bulk INSERT via Core (not the ORM), returning ids in ``rows`` order.

        For callers that need ids back immediately but not real ORM/
        session-tracked objects — contrast ``bulk_create`` (returns real
        objects, one INSERT per call but ORM-instantiates every row first)
        and ``bulk_copy`` (COPY, fastest, but never populates ids at all).
        ``rows`` are plain column-value dicts: no ``DataEntry(...)``
        construction, so none of the per-instance SQLAlchemy mapper/
        Pydantic-validation cost `DataEntryEmissionRow` was introduced to
        avoid (plan #2050 §C2/C3) applies here either — the same tax on the
        model one level up.

        ``sort_by_parameter_order`` is SQLAlchemy's documented guarantee
        that RETURNING rows line up with ``rows``' order — the only
        contractual way to get that; without it, ordering is
        implementation-defined per backend/driver/batch-size, not something
        to rely on even where it happens to work in ad hoc testing (checked
        up to N=2000 against local Postgres/psycopg — order held either
        way here, but that's this stack's current behavior, not the API
        contract). insertmanyvalues still batches every row into one round
        trip on Postgres regardless of count. Requires the
        params-as-second-argument form of ``execute`` — a multi-row
        ``.values(rows)`` INSERT can't be order-sorted (verified; raises
        ``CompileError``).
        """
        if not rows:
            return []
        stmt = insert(DataEntry).returning(
            col(DataEntry.id), sort_by_parameter_order=True
        )
        result = await self.session.execute(stmt, rows)
        return [row[0] for row in result.all()]

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
        """Bulk delete data entries by module, type, and source.

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

    async def bulk_delete_by_modules(self, carbon_report_module_ids: list[int]) -> int:
        """Delete every data entry of the given modules. Returns the row count.

        Used by the Simulator Plan when a plan-year's reference year changes:
        the prefilled modules are emptied before being rebuilt from the new
        baseline. Emissions follow through the ``data_entry_id`` cascade.
        """
        if not carbon_report_module_ids:
            return 0
        statement = delete(DataEntry).where(
            col(DataEntry.carbon_report_module_id).in_(carbon_report_module_ids)
        )
        result = await self.session.execute(statement)
        await self.session.flush()
        return getattr(result, "rowcount", 0) or 0

    async def bulk_delete_by_source_year(
        self,
        year: int,
        data_entry_type_ids: list[int],
        sources: list[int],  # DataEntrySourceEnum values
    ) -> int:
        """Full-year replace delete for MODULE_PER_YEAR ingest.

        Per-year feeds (CSV or API) are complete exports: a new ingest
        replaces ALL prior rows of that (year, type) across the given
        sources regardless of unit, so the delete keys on the
        denormalized ``data_entries.year`` column — no module-tree
        resolution, one indexed statement.  Returns the number of rows
        deleted.
        """
        if not data_entry_type_ids or not sources:
            return 0
        statement = delete(DataEntry).where(
            col(DataEntry.year) == year,
            col(DataEntry.data_entry_type_id).in_(data_entry_type_ids),
            col(DataEntry.source).in_(sources),
        )
        result = await self.session.execute(statement)
        await self.session.flush()
        return getattr(result, "rowcount", 0) or 0

    async def update(
        self, id: int, data: DataEntryUpdate, user_id: int
    ) -> DataEntry | None:
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

    async def get_member_role_keys(
        self, carbon_report_module_ids: list[int]
    ) -> set[tuple[int, str, str]]:
        """Bulk-fetch existing member (module, uid, sius_code) role keys.

        Seeds the CSV ingest's in-memory duplicate set in ONE query so the
        row loop never round-trips per row — the per-row
        ``check_member_role_unique`` SELECT at stage latencies turned an
        8.5k-row parse into ~10 minutes (14 rows/s, 2026-07-17), the same
        N+1 shape the COPY batching already removed on the write side.

        Snapshot semantics: concurrent bulk writers are serialized by the
        per-(module_type, year) advisory lock at dispatch, but that lock is
        transaction-scoped and drops at each batch commit, so a writer
        committing mid-file is invisible to an already-taken snapshot. The
        airtight guard is the DB-enforced partial unique index deferred in
        the 1564 incident plan; until then this is no weaker than the old
        per-row check-then-COPY, just a wider read-to-write window.
        """
        if not carbon_report_module_ids:
            return set()
        stmt = select(
            col(DataEntry.carbon_report_module_id),
            DataEntry.data["user_institutional_id"].as_string(),
            DataEntry.data["sius_code"].as_string(),
        ).where(
            col(DataEntry.carbon_report_module_id).in_(carbon_report_module_ids),
            col(DataEntry.data_entry_type_id) == DataEntryTypeEnum.member.value,
        )
        rows = (await self.session.execute(stmt)).all()
        return {
            (module_id, uid, sius)
            for module_id, uid, sius in rows
            if uid is not None and sius is not None
        }

    async def check_json_field_unique(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        fields: dict[str, str],
        exclude_id: int | None = None,
    ) -> bool:
        """Check whether a set of JSON data field values is unique within a submodule.

        Args:
            carbon_report_module_id: The module to scope the check to.
            data_entry_type_id: The submodule type.
            fields: JSON keys inside ``DataEntry.data`` mapped to the values that
                must be unique together (ANDed). A single-entry dict reproduces
                the previous single-field check.
            exclude_id: Optional entry ID to exclude (for PATCH uniqueness checks).

        Returns:
            True if the combination is unique (no conflicting row found), False
            otherwise.
        """
        statement = (
            select(DataEntry)
            .where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                col(DataEntry.data_entry_type_id) == data_entry_type_id,
                *[
                    DataEntry.data[key].as_string() == val
                    for key, val in fields.items()
                ],
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
        filter: str | None = None,
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

    async def list_by_carbon_report(self, carbon_report_id: int) -> list[DataEntry]:
        """Fetch all DataEntries belonging to one carbon report."""
        statement = (
            select(DataEntry)
            .join(
                CarbonReportModule,
                col(DataEntry.carbon_report_module_id) == col(CarbonReportModule.id),
            )
            .where(col(CarbonReportModule.carbon_report_id) == carbon_report_id)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_by_module(self, carbon_report_module_id: int) -> list[DataEntry]:
        """Fetch all DataEntries of one carbon report module."""
        statement = select(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_by_data_entry_type_and_year(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
        carbon_report_module_ids: list[int] | None = None,
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
    ) -> int | None:
        return await self.carbon_report_module_repo.get_module_type(
            carbon_report_module_id
        )

    async def get_total_count_by_submodule(
        self,
        carbon_report_module_id: int,
        travel_institutional_id_filter: str | None = None,
        exclude_planner_snapshots: bool = False,
    ) -> dict[int, int]:
        """Docstring for get_total_count_by_submodule

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
        if exclude_planner_snapshots:
            query = query.where(
                col(DataEntry.source).is_distinct_from(
                    DataEntrySourceEnum.PLANNER_SNAPSHOT.value
                )
            )
        result = await self.session.execute(query)
        rows = list(result.all())
        aggregation: dict[int, int] = {
            data_entry_type_id: int(total_count)
            for data_entry_type_id, total_count in rows
        }

        # Fill in zeros for missing types
        for type_id in all_type_ids:
            if type_id not in aggregation:
                aggregation[type_id] = 0

        return aggregation

    def _apply_name_filter(self, statement, filter: str | None, filter_map: dict):
        """Applies a filter to the given SQLAlchemy statement using the
        caller-prepared (possibly lateral-adapted) filter_map.
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
            # Build OR conditions for all filter fields
            conditions = [
                filter_expr.ilike(filter_pattern) for filter_expr in filter_map.values()
            ]
            statement = statement.where(or_(*conditions))
        return statement, filter_pattern

    def _resolved_factor_id(self, handler: Any, data_entry_type_id: int) -> Any:
        """SQL twin of ``FactorResolver`` for list queries.

        Correlated scalar subquery returning, per entry row, the id of the
        factor the resolver would pick — deterministic because the reupload
        sweep keeps a single factor generation per
        ``(det, year, classification)``.  Joining ``Factor`` on this id
        makes factor-backed sort/filter/pagination work for every row,
        including entries whose emissions are not computed yet.

        Chain parity: exact ``(kind, subkind)`` beats the subkind-less row;
        for override handlers an override-code match beats the code-less
        average row.  Divergences (display-only, accepted): matching is
        kind-anchored — a code match under a *different* kind is not
        considered — and ambiguity resolves to the lowest id instead of
        raising; compute/update paths keep the loud semantics.
        """
        f = aliased(Factor)
        kind_field: str = handler.kind_field
        entry_kind = DataEntry.data[kind_field].as_string()
        conditions = [
            col(f.data_entry_type_id) == data_entry_type_id,
            col(f.year) == col(DataEntry.year),
            f.classification[kind_field].as_string() == entry_kind,
        ]
        ordering: list[Any] = []
        override_field = handler.kind_field_override
        subkind_field = handler.subkind_field
        # Preference ordering must not reference outer columns (sqlite
        # rejects correlated ORDER BY): within the WHERE-filtered candidate
        # set, carrying a subkind/override code IS the exact match, so
        # "specific first" reduces to a non-correlated IS NOT NULL sort.
        if override_field is not None:
            f_code = f.classification[override_field].as_string()
            d_code = DataEntry.data[override_field].as_string()
            conditions.append(or_(f_code == d_code, f_code.is_(None)))
            ordering = [f_code.isnot(None).desc()]
        elif subkind_field is not None:
            f_sub = f.classification[subkind_field].as_string()
            d_sub = DataEntry.data[subkind_field].as_string()
            conditions.append(or_(f_sub == d_sub, f_sub.is_(None)))
            ordering = [f_sub.isnot(None).desc()]
        return (
            sa_select(col(f.id))
            .where(*conditions)
            .order_by(*ordering, col(f.id))
            .limit(1)
            .scalar_subquery()
        )

    def _apply_sort(self, statement, sort_by: str, sort_order: str, sort_map: dict):
        sort_expr = sort_map.get(sort_by)
        if sort_expr is None:
            raise ValueError(f"Cannot sort by unknown field: {sort_by}")
        if sort_order.lower() == "asc":
            return statement.order_by(asc(sort_expr))
        else:
            return statement.order_by(desc(sort_expr))

    async def _prior_equipment_year(
        self, unit_id: int, current_year: int
    ) -> int | None:
        """Return the unit's most recent year with equipment entries strictly
        before ``current_year`` — robust to skipped years. ``None`` when the
        unit has no earlier equipment data (e.g. its first campaign year).
        """
        prior_year = (
            await self.session.execute(
                select(func.max(DataEntry.year)).where(
                    col(DataEntry.unit_id) == unit_id,
                    col(DataEntry.year) < current_year,
                    col(DataEntry.data_entry_type_id).in_(
                        list(EQUIPMENT_DATA_ENTRY_TYPE_IDS)
                    ),
                )
            )
        ).scalar_one_or_none()
        return int(prior_year) if prior_year is not None else None

    async def get_prior_year_equipment_ids(
        self, unit_id: int, current_year: int
    ) -> set[str]:
        """Return the set of ``equipment_id`` present in the unit's most recent
        prior year (issue #259). Empty set when there is no prior-year
        equipment data, in which case nothing is flagged new.

        Ingest-only since #2050 J10: called once per (unit, year) while a CSV
        lands, never per page render.
        """
        prior_year = await self._prior_equipment_year(unit_id, current_year)
        if prior_year is None:
            return set()
        equipment_id = DataEntry.data["equipment_id"].as_string()
        rows = (
            (
                await self.session.execute(
                    select(equipment_id)
                    .where(
                        col(DataEntry.unit_id) == unit_id,
                        col(DataEntry.year) == prior_year,
                        col(DataEntry.data_entry_type_id).in_(
                            list(EQUIPMENT_DATA_ENTRY_TYPE_IDS)
                        ),
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        return {r for r in rows if r is not None}

    async def get_prior_year_equipment_usage(
        self, unit_id: int, current_year: int
    ) -> dict[str, dict]:
        """Map ``equipment_id`` -> usage values set in the unit's most recent
        prior year (issue #259 carry-forward).

        Single query per (unit, year): only the ``equipment_id`` and the two
        usage fields travel over the wire, so a 50k-row prior year stays cheap.
        Only fields actually set in the prior row appear in each dict, so the
        caller can merge without inventing values the prior year never had.
        """
        prior_year = await self._prior_equipment_year(unit_id, current_year)
        if prior_year is None:
            return {}
        rows = (
            await self.session.execute(
                select(
                    DataEntry.data["equipment_id"].as_string(),
                    *(DataEntry.data[field] for field in EQUIPMENT_USAGE_FIELDS),
                )
                .where(
                    col(DataEntry.unit_id) == unit_id,
                    col(DataEntry.year) == prior_year,
                    col(DataEntry.data_entry_type_id).in_(
                        list(EQUIPMENT_DATA_ENTRY_TYPE_IDS)
                    ),
                )
                .order_by(col(DataEntry.id))
            )
        ).all()
        usage_by_equipment: dict[str, dict] = {}
        for equipment_id, *values in rows:
            if not equipment_id:
                continue
            usage = {
                field: value
                for field, value in zip(EQUIPMENT_USAGE_FIELDS, values)
                if value is not None
            }
            if not usage:
                continue
            usage_by_equipment.setdefault(equipment_id, {}).update(usage)
        return usage_by_equipment

    async def _equipment_module_scope(
        self, carbon_report_module_id: int
    ) -> tuple[int, int] | None:
        """Return ``(unit_id, year)`` for an Equipment module, or ``None`` when
        the module has no equipment entries to derive them from.
        """
        meta = (
            await self.session.execute(
                select(DataEntry.unit_id, DataEntry.year)
                .where(
                    col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                    col(DataEntry.data_entry_type_id).in_(
                        list(EQUIPMENT_DATA_ENTRY_TYPE_IDS)
                    ),
                )
                .limit(1)
            )
        ).first()
        if meta is None or meta[0] is None or meta[1] is None:
            return None
        return int(meta[0]), int(meta[1])

    async def count_incomplete_new_equipment(self, carbon_report_module_id: int) -> int:
        """Count equipment that is new vs the previous year (issue #259) yet is
        still missing usage data (active or standby hours). Returns ``0`` for
        non-equipment modules, so it is safe to call unconditionally on any
        module.

        #2050 J11: reads the ``is_new`` flag stamped at ingest
        (``DataEntryService.apply_equipment_carry_forward``) rather than
        re-deriving it. It used to load every ``equipment_id`` in the unit's
        prior year and inline the set as ``NOT IN (...)`` — and unlike the
        equipment page, this runs on *every* module GET.
        """
        active = DataEntry.data["active_usage_hours_per_week"].as_string()
        standby = DataEntry.data["standby_usage_hours_per_week"].as_string()
        count = (
            await self.session.execute(
                select(func.count())
                .select_from(DataEntry)
                .where(
                    col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                    col(DataEntry.data_entry_type_id).in_(
                        list(EQUIPMENT_DATA_ENTRY_TYPE_IDS)
                    ),
                    DataEntry.data["is_new"].as_boolean(),
                    or_(active.is_(None), standby.is_(None)),
                )
            )
        ).scalar_one()
        return int(count)

    async def get_submodule_data(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
        filter: str | None = None,
        institutional_id_filter: str | None = None,
        exclude_planner_snapshots: bool = False,
    ) -> SubmoduleResponse:
        is_travel_entry = data_entry_type_id in (
            DataEntryTypeEnum.plane.value,
            DataEntryTypeEnum.train.value,
        )
        is_train_entry = data_entry_type_id == DataEntryTypeEnum.train.value
        is_plane_entry = data_entry_type_id == DataEntryTypeEnum.plane.value
        OriginLocation: Any = None
        DestLocation: Any = None
        traveler_name_subq: Any = None
        is_buildings_entry = data_entry_type_id in (
            DataEntryTypeEnum.building.value,
            DataEntryTypeEnum.building_embodied_energy.value,
        )
        is_headcount_entry = data_entry_type_id in (
            DataEntryTypeEnum.member.value,
            DataEntryTypeEnum.student.value,
            # #2050 Track H: planner_headcount already gets a rollup row
            # from prepare_create (DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION maps
            # it to EmissionType.headcount, same as member/student) — it
            # was just never wired to read it, so it fell through to the
            # unfiltered whole-table aggregation below (825ms in production).
            DataEntryTypeEnum.planner_headcount.value,
        )
        is_equipment_entry = data_entry_type_id in EQUIPMENT_DATA_ENTRY_TYPE_IDS
        handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum(data_entry_type_id))

        # Classification-resolved factor in SQL (plan 1661-sql-factor-resolution):
        # used for every handler whose kind lives in entry.data. Travel and
        # headcount derive their kind at compute time, so their factor display
        # keeps coming from the computed emission rows below.
        resolved_factor_id: Any = None
        # Filter conditions may reference Factor columns; the count query
        # must join Factor exactly like the page query or it degenerates to
        # an implicit cross join (0 or inflated counts). Each branch records
        # its join chain here.
        count_factor_joins: list[tuple[Any, Any]] = []
        count_location_joins: list[tuple[Any, Any]] = []
        if (
            not is_travel_entry
            and not is_headcount_entry
            and handler.kind_field is not None
        ):
            resolved_factor_id = self._resolved_factor_id(handler, data_entry_type_id)

        # The entries this page can possibly show. Both aggregation subqueries
        # below restrict to it: a GROUP BY over the whole data_entry_emissions
        # table cannot be narrowed by the outer WHERE (#2050 J8).
        module_entry_ids = select(col(DataEntry.id)).where(
            col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
            col(DataEntry.data_entry_type_id) == data_entry_type_id,
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
            # #2050 J8: restricted to this module's entries — see the generic
            # branch below for why an unrestricted GROUP BY here scans the
            # whole emissions table on every request.
            building_emission_agg_q = (
                select(
                    DataEntryEmission.data_entry_id,
                    func.sum(DataEntryEmission.kg_co2eq).label("total_kg_co2eq"),
                )
                .where(col(DataEntryEmission.data_entry_id).in_(module_entry_ids))
                .group_by(col(DataEntryEmission.data_entry_id))
            )
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
                    col(Factor.id) == resolved_factor_id,
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
            count_factor_joins = [
                (Factor, col(Factor.id) == resolved_factor_id),
                (
                    BuildingRoom,
                    DataEntry.data["room_name"].as_string()
                    == col(BuildingRoom.room_name),
                ),
            ]
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
                col(RollupEmission.kg_co2eq).label("total_kg_co2eq"),
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
            count_factor_joins = [
                (
                    RollupEmission,
                    (col(RollupEmission.data_entry_id) == col(DataEntry.id))
                    & (col(RollupEmission.emission_type_id) == rollup_et_id)
                    & (col(RollupEmission.scope).is_(None)),
                ),
                (Factor, col(RollupEmission.primary_factor_id) == col(Factor.id)),
            ]
        else:
            # --- Aggregation subquery for multi-emission entries ---
            # Exclude rollup rows so future rollup types are never double-counted.
            #
            # #2050 J8: restricted to this module's entries. Without it the
            # GROUP BY runs over every row in data_entry_emissions (250k-1M in
            # real environments) and the join then discards all but this page's
            # — the outer WHERE cannot help, since a predicate cannot be pushed
            # through a GROUP BY. That cost a 648ms GET on dev for a submodule
            # holding one entry. Same restriction
            # get_professional_travel_trip_legs already applies for the same
            # reason.
            emission_agg_q = (
                select(
                    DataEntryEmission.data_entry_id,
                    func.sum(DataEntryEmission.kg_co2eq).label("total_kg_co2eq"),
                    func.min(DataEntryEmission.primary_factor_id).label(
                        "primary_factor_id"
                    ),
                )
                .where(col(DataEntryEmission.data_entry_id).in_(module_entry_ids))
                .group_by(col(DataEntryEmission.data_entry_id))
            )
            if ROLLUP_EMISSION_TYPE_IDS:
                emission_agg_q = emission_agg_q.where(
                    col(DataEntryEmission.emission_type_id).notin_(
                        ROLLUP_EMISSION_TYPE_IDS
                    )
                )
            emission_agg = emission_agg_q.subquery()

            entities = [DataEntry, emission_agg.c.total_kg_co2eq, Factor]
            if is_travel_entry:
                # Both TRAVELER_OTHER_INTERNAL ("-1") and External-other
                # (real SQL NULL) rely on this equality never spuriously
                # matching a MemberEntry: no real SCIPER is ever "-1", and
                # SQL's NULL = NULL evaluates to NULL (not true) — so an
                # External-other travel row can never match a Headcount
                # member who also has no SCIPER yet (#951 made that
                # optional too). See
                # 1153-traveler-sentinel-resolution-prd.md §5.
                # A person can hold multiple headcount roles (sius_code) in the
                # same unit, so a plain JOIN on (uid, module) can match >1
                # MemberEntry row and fan out/duplicate every travel row for
                # that person. traveler_name is identical across roles, so pick
                # one match deterministically via a correlated scalar subquery
                # (same pattern as list_units's latest_stats_subq; LATERAL
                # JOIN is avoided — unsupported on SQLite, used in unit tests).
                # Tie-break on lowest id: always present, unlike sius_code
                # which can be null on legacy rows.
                traveler_name_subq = (
                    select(MemberEntry.data["name"].as_string())
                    .where(
                        MemberEntry.data["user_institutional_id"].as_string()
                        == DataEntry.data["user_institutional_id"].as_string(),
                        col(MemberEntry.carbon_report_module_id)
                        == col(DataEntry.carbon_report_module_id),
                        col(MemberEntry.data_entry_type_id)
                        == DataEntryTypeEnum.member.value,
                    )
                    .order_by(asc(col(MemberEntry.id)))
                    .limit(1)
                    .correlate(DataEntry)
                    .scalar_subquery()
                )
                entities.extend(
                    [traveler_name_subq.label("traveler_name"), DataEntryEmission]
                )
                if is_train_entry or is_plane_entry:
                    OriginLocation = aliased(Location)
                    DestLocation = aliased(Location)
                    entities.extend([OriginLocation, DestLocation])
            statement = sa_select(*entities).join(
                emission_agg,
                col(DataEntry.id) == emission_agg.c.data_entry_id,
                isouter=True,
            )
            factor_on = (
                col(Factor.id) == resolved_factor_id
                if resolved_factor_id is not None
                else emission_agg.c.primary_factor_id == col(Factor.id)
            )
            statement = statement.join(Factor, factor_on, isouter=True)
            count_factor_joins = (
                [(Factor, factor_on)]
                if resolved_factor_id is not None
                else [
                    (emission_agg, col(DataEntry.id) == emission_agg.c.data_entry_id),
                    (Factor, factor_on),
                ]
            )

            if is_travel_entry:
                statement = statement.join(
                    DataEntryEmission,
                    col(DataEntryEmission.data_entry_id) == DataEntry.id,
                    isouter=True,
                )
                if is_train_entry:
                    statement = statement.join(
                        OriginLocation,
                        (
                            col(OriginLocation.name)
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
                            col(DestLocation.name)
                            == DataEntry.data["destination_name"].as_string()
                        )
                        & (col(DestLocation.transport_mode) == TransportModeEnum.train),
                        isouter=True,
                    )
                elif is_plane_entry:
                    plane_origin_on = (
                        col(OriginLocation.iata_code)
                        == DataEntry.data["origin_iata"].as_string()
                    ) & (col(OriginLocation.transport_mode) == TransportModeEnum.plane)
                    plane_dest_on = (
                        col(DestLocation.iata_code)
                        == DataEntry.data["destination_iata"].as_string()
                    ) & (col(DestLocation.transport_mode) == TransportModeEnum.plane)
                    statement = statement.join(
                        OriginLocation, plane_origin_on, isouter=True
                    ).join(DestLocation, plane_dest_on, isouter=True)
                    count_location_joins = [
                        (OriginLocation, plane_origin_on),
                        (DestLocation, plane_dest_on),
                    ]
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

        if exclude_planner_snapshots:
            statement = statement.where(
                col(DataEntry.source).is_distinct_from(
                    DataEntrySourceEnum.PLANNER_SNAPSHOT.value
                )
            )

        handler_default = getattr(handler, "default_where", [])
        if handler_default:
            statement = statement.where(*handler_default)
        filter_map = dict(getattr(handler, "filter_map", {}) or DEFAULT_FILTER_MAP)
        if is_plane_entry and OriginLocation is not None:
            for prefix, loc in (
                ("origin", OriginLocation),
                ("destination", DestLocation),
            ):
                filter_map[f"{prefix}_name"] = loc.name
                filter_map[f"{prefix}_municipality"] = loc.municipality
                filter_map[f"{prefix}_keywords"] = loc.keywords
        statement, filter_pattern = self._apply_name_filter(
            statement, filter, filter_map
        )

        sort_map = dict(
            handler.sort_map
        )  # shallow copy — don't mutate the class-level dict
        sort_map["kg_co2eq"] = kg_sort_expr
        if is_buildings_entry:
            # Surface lives on the joined building_rooms row (synced from the
            # buildings source), not in entry data — the class-level map entry
            # would sort all-NULL. Entry data stays as fallback for rows
            # carrying an inline value.
            sort_map["room_surface_square_meter"] = func.coalesce(
                col(BuildingRoom.room_surface_square_meter),
                DataEntry.data["room_surface_square_meter"].as_float(),
            )
        if is_travel_entry:
            sort_map["distance_km"] = func.coalesce(
                DataEntryEmission.additional_value,
                DataEntry.data["distance_km"].as_float(),
            )
            # The class-level sort_map's "traveler_name" references MemberEntry
            # directly, which relied on the (now-removed) plain JOIN. Point it at
            # the same correlated subquery used for enrichment above, or sorting
            # by traveler_name would silently reintroduce an unjoined MemberEntry
            # reference (implicit cross join).
            sort_map["traveler_name"] = traveler_name_subq
        if (is_train_entry or is_plane_entry) and OriginLocation is not None:
            sort_map["origin_name"] = OriginLocation.name
            sort_map["destination_name"] = DestLocation.name

        if is_equipment_entry:
            # #2050 J10: ``is_new`` is stamped at ingest and stored on the row
            # (DataEntryService.apply_equipment_carry_forward), so this reads
            # it instead of re-deriving it. Deriving it here meant pulling the
            # unit's entire prior-year id set into Python and inlining it as
            # thousands of bind parameters — 1711ms on dev to render 20 rows.
            is_new_expr = DataEntry.data["is_new"].as_boolean()
            missing_usage_expr = or_(
                DataEntry.data["active_usage_hours_per_week"].as_string().is_(None),
                DataEntry.data["standby_usage_hours_per_week"].as_string().is_(None),
            )
            # New equipment still missing its usage floats to the top.
            statement = statement.order_by(desc(and_(is_new_expr, missing_usage_expr)))

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
        if exclude_planner_snapshots:
            count_stmt = count_stmt.where(
                col(DataEntry.source).is_distinct_from(
                    DataEntrySourceEnum.PLANNER_SNAPSHOT.value
                )
            )
        if handler_default:
            count_stmt = count_stmt.where(*handler_default)
        if filter_pattern != "":
            # Only pay for the factor join chain when a filter expression
            # actually reads it — buildings/purchase/RF filters are pure
            # entry-data and skip the per-row factor subquery entirely.
            filter_reads_factor = any(
                "factors" in str(expr) or "building_rooms" in str(expr)
                for expr in filter_map.values()
            )
            needs_factor_joins = bool(count_factor_joins) and filter_reads_factor
            if needs_factor_joins or count_location_joins:
                # Join Factor/Location (and whatever they hang off) exactly
                # like the page query so the count sees the same rows —
                # without this a joined-table filter degenerates into an
                # implicit cross join (0 or inflated counts).
                count_stmt = count_stmt.select_from(DataEntry)
            if needs_factor_joins:
                for target, onclause in count_factor_joins:
                    count_stmt = count_stmt.join(target, onclause, isouter=True)
            for target, onclause in count_location_joins:
                count_stmt = count_stmt.join(target, onclause, isouter=True)
            conditions = [
                filter_expr.ilike(filter_pattern) for filter_expr in filter_map.values()
            ]
            count_stmt = count_stmt.where(or_(*conditions))
        total_items = (await self.session.execute(count_stmt)).scalar_one()
        rows = result.all()
        count = len(rows)

        # Planner snapshot rows carry ``source_data_entry_id`` — the reference-
        # year entry they were copied from. Expose that source's emissions as
        # ``reference_kg_co2eq`` (the 100% baseline the "% of reference year"
        # slider scales from), batched into one grouped query for the page.
        # Calculator rows have no source id, so this is a no-op there.
        reference_kg_by_source = await self._reference_kg_by_source_ids(
            [
                int(sid)
                for row in rows
                if (sid := row[0].data.get("source_data_entry_id")) is not None
            ]
        )

        items: list[BaseModel] = []

        for row in rows:
            # Pre-bind conditionally-unpacked variables so static type checkers
            # see them as definitely-bound (T | None) on every branch path.
            traveler_name: str | None = None
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
                    traveler_name, _emission, _origin_loc, _dest_loc = row[3:]
                else:
                    traveler_name, _emission = row[3:]
            elif is_buildings_entry:
                building_room = row[3]

            # Defense-in-depth: detach loaded ORM rows from the session so any
            # accidental mutation (here or downstream) cannot be flushed back to
            # the DB. This method only reads scalar columns and the JSON `data`
            # field after unpack — no lazy relationships — so expunge is safe.
            # traveler_name is a plain scalar (from a subquery), not an ORM row,
            # so it needs no detaching.
            self._detach(data_entry, primary_factor)
            if is_travel_entry:
                self._detach(_emission, _origin_loc, _dest_loc)
            elif is_buildings_entry:
                self._detach(building_room)

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

            if is_equipment_entry:
                enriched_data["is_new"] = bool(data_entry.data.get("is_new", False))

            if is_travel_entry:
                distance_km = (
                    float(_emission.additional_value)
                    if _emission is not None and _emission.additional_value is not None
                    else enriched_data.get("distance_km")
                )
                if traveler_name is not None:
                    enriched_data["traveler_name"] = traveler_name
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
                # Embodied rows persist only room_name — building_name is
                # reference data; parents keep their own stored value.
                if (
                    data_entry_type_id
                    == DataEntryTypeEnum.building_embodied_energy.value
                ):
                    enriched_data["building_name"] = building_room.building_name

            source_entry_id = data_entry.data.get("source_data_entry_id")
            if source_entry_id is not None:
                enriched_data["reference_kg_co2eq"] = reference_kg_by_source.get(
                    int(source_entry_id)
                )

            try:
                items.append(handler.to_response(data_entry, enriched_data))
            except ValidationError as exc:
                raise ValueError(
                    f"data_entry id={data_entry.id} "
                    f"(type={data_entry_type_id}) does not match the "
                    f"response schema"
                ) from exc

        response = SubmoduleResponse(
            id=data_entry_type_id,
            count=len(items),
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

    async def _reference_kg_by_source_ids(
        self, source_ids: list[int]
    ) -> dict[int, float]:
        """Sum persisted kg_co2eq per source data entry (planner snapshots).

        One grouped query for the whole page; empty in → empty out. Mirrors
        ``DataEntryEmissionService._sum_entry_emissions`` (raw kg over the
        entry's leaves) so the reference column matches the % override base.
        """
        if not source_ids:
            return {}
        stmt = (
            select(
                DataEntryEmission.data_entry_id,
                func.sum(DataEntryEmission.kg_co2eq),
            )
            .where(col(DataEntryEmission.data_entry_id).in_(source_ids))
            .group_by(col(DataEntryEmission.data_entry_id))
        )
        rows = (await self.session.exec(stmt)).all()
        return {int(entry_id): float(total or 0.0) for entry_id, total in rows}

    async def get_professional_travel_trip_legs(
        self,
        carbon_report_module_id: int,
        institutional_id_filter: str | None = None,
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
                    col(OriginLocation.natural_key) == origin_key,
                    isouter=True,
                )
                .join(
                    DestLocation,
                    col(DestLocation.natural_key) == dest_key,
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

    async def get_headcount_fte_breakdown(
        self, carbon_report_module_id: int
    ) -> HeadcountFteBreakdown:
        """Every FTE figure the headcount module page needs, in one query.

        The route used to ask three times over the same table, module and
        field — total, members grouped by sius_code, students — and on dev
        each round trip costs ~160ms (#2050 Track G2). One GROUP BY over
        ``(data_entry_type_id, sius_code)`` carries all three.
        """
        sius_code = DataEntry.data["sius_code"].as_string()
        fte = DataEntry.data["fte"].as_float()
        statement = (
            select(
                col(DataEntry.data_entry_type_id),
                sius_code.label("sius_code"),
                func.sum(fte).label("total_fte"),
            )
            .where(col(DataEntry.carbon_report_module_id) == carbon_report_module_id)
            .group_by(col(DataEntry.data_entry_type_id), sius_code)
        )
        rows = (await self.session.execute(statement)).all()

        total_fte = 0.0
        student_fte = 0.0
        member_fte_by_sius_code: dict[str, float | None] = {}
        for data_entry_type_id, code, group_fte in rows:
            total_fte += group_fte or 0.0
            if data_entry_type_id == DataEntryTypeEnum.student.value:
                student_fte += group_fte or 0.0
            if data_entry_type_id == DataEntryTypeEnum.member.value:
                # A NULL sum stays None rather than 0.0 — the group exists
                # but has no FTE recorded, which is not the same as zero.
                label = str(code) if code is not None else "unknown"
                member_fte_by_sius_code[label] = group_fte
        # Deterministic bar order for the chart: 51…59, then Other staff.
        member_fte_by_sius_code = {
            k: member_fte_by_sius_code[k]
            for k in sorted(
                member_fte_by_sius_code, key=lambda k: (k == OTHER_SIUS_CODE, k)
            )
        }
        return HeadcountFteBreakdown(
            total_fte=total_fte,
            student_fte=student_fte,
            member_fte_by_sius_code=member_fte_by_sius_code,
        )

    async def get_total_per_field(
        self,
        field_name: str,
        carbon_report_module_id: int,
        data_entry_type_id: int | None = None,
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
        data_entry_type_id: int | None = None,
    ) -> dict[str, float | None]:
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
        aggregation: dict[str, float | None] = {}
        for key, total_count in rows:
            label = str(key) if key is not None else "unknown"
            if label not in aggregation:
                aggregation[label] = None
            if total_count is not None:
                aggregation[label] = (aggregation[label] or 0.0) + total_count

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
    ) -> dict | None:
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
