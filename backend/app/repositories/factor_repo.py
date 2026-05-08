"""Repository for generic factors."""

from typing import Dict, List, Optional

from sqlalchemy import case, or_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import (
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    ModuleTypeEnum,
)
from app.schemas.data_entry import BaseModuleHandler


class FactorRepository:
    """Repository for factor CRUD operations and lookups."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: int) -> Optional[Factor]:
        """Get factor by ID."""
        stmt = select(Factor).where(col(Factor.id) == id)
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_current_factor(
        self,
        emission_type_id: EmissionType,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
    ) -> Optional[Factor]:
        """
        Get the current (valid_to IS NULL) factor for given criteria.

        Args:
            emission_type_id: Emission type filter
            data_entry_type_id: Data entry type filter
            year: Year filter for year-scoped factors (mandatory)
        """
        conditions = [
            col(Factor.emission_type_id) == emission_type_id,
            col(Factor.data_entry_type_id) == data_entry_type_id,
            col(Factor.year) == year,
        ]

        stmt = select(Factor).where(*conditions)

        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def create(self, factor: Factor) -> Factor:
        """Create a new factor."""
        self.session.add(factor)
        await self.session.flush()
        await self.session.refresh(factor)
        return factor

    async def bulk_create(self, factors: List[Factor]) -> List[Factor]:
        """Bulk create factors."""
        self.session.add_all(factors)
        await self.session.flush()
        for factor in factors:
            await self.session.refresh(factor)
        return factors

    async def upsert_factors(
        self,
        factors: List[Factor],
        current_job_id: int,
    ) -> int:
        """Insert-or-update factors keyed on the identity index.

        Identity key is ``(data_entry_type_id, year, emission_type_id,
        classification::text)``. Two partial unique indexes back this
        (``year IS NOT NULL`` vs ``year IS NULL``) because NULL ≠ NULL in a
        unique index expression — so the input must be split by year-presence
        and one ON CONFLICT inference issued per partition.

        Preserves ``factor.id`` for existing rows so downstream
        references — including ``primary_factor_id`` values stored in
        ``DataEntry.data`` (a JSON value, not a real FK column) — stay
        valid across reuploads.  Stamps ``last_seen_job_id`` so callers
        can later detect rows not present in the current batch.

        Postgres-only: relies on ``INSERT ... ON CONFLICT DO UPDATE``.

        Returns the number of rows affected (insert + update).
        """
        if not factors:
            return 0

        with_year: List[Factor] = []
        no_year: List[Factor] = []
        for f in factors:
            if f.year is not None:
                with_year.append(f)
            else:
                no_year.append(f)

        affected = 0
        if with_year:
            affected += await self._upsert_subset(
                with_year, current_job_id, year_present=True
            )
        if no_year:
            affected += await self._upsert_subset(
                no_year, current_job_id, year_present=False
            )
        return affected

    async def _upsert_subset(
        self,
        factors: List[Factor],
        current_job_id: int,
        *,
        year_present: bool,
    ) -> int:
        payload = [
            {
                **f.model_dump(exclude={"id", "last_seen_job_id"}),
                "last_seen_job_id": current_job_id,
            }
            for f in factors
        ]
        stmt = pg_insert(Factor).values(payload)

        # Conflict target must match the partial index exactly: same column
        # list (with the (classification::text) functional element) and
        # same WHERE predicate.
        if year_present:
            index_elements: list = [
                "data_entry_type_id",
                "year",
                "emission_type_id",
                text("(classification::text)"),
            ]
            index_where = text("year IS NOT NULL")
        else:
            index_elements = [
                "data_entry_type_id",
                "emission_type_id",
                text("(classification::text)"),
            ]
            index_where = text("year IS NULL")

        # Bracket access on excluded avoids the .values name clash with
        # Insert.values().
        stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            index_where=index_where,
            set_={
                "values": stmt.excluded["values"],
                "last_seen_job_id": stmt.excluded["last_seen_job_id"],
            },
        )
        result = await self.session.execute(stmt)
        # rowcount is a CursorResult attribute on DML; cast away the
        # narrower Result[Any] type Pyright infers from session.execute.
        return getattr(result, "rowcount", 0) or 0

    async def _latest_factor_job_per_det(self, year: int) -> Dict[int, int]:
        """Resolve the most recent ``is_current`` finished FACTORS job that
        covers each ``data_entry_type_id`` for the given year.

        Multi-type CSV uploads (e.g. ``equipments_factors.csv``) create a
        single FACTORS job with ``data_entry_type_id=NULL`` and
        ``module_type_id`` set; that one job covers every det in the
        module via ``MODULE_TYPE_TO_DATA_ENTRY_TYPES``.  A naive SQL join
        on ``Factor.det = Job.det`` misses these uploads (NULL ≠ any det),
        so we expand them in Python.  Cardinality of "is_current FACTORS
        jobs for one year" is small (one per active module / det), so
        loading them in-process is cheap.

        Returns:
            Map from ``data_entry_type_id`` to the highest job id that
            wrote factors for that det in this year.
        """
        # Restrict to ingestion_method=csv: ``last_seen_job_id`` is only
        # stamped by the CSV upsert path.  If a ``computed`` FACTORS job
        # ever becomes is_current its higher id would shadow the latest
        # CSV upload and make every csv-stamped factor look stale.
        stmt = select(
            DataIngestionJob.id,
            DataIngestionJob.module_type_id,
            DataIngestionJob.data_entry_type_id,
        ).where(
            col(DataIngestionJob.year) == year,
            col(DataIngestionJob.target_type) == TargetType.FACTORS,
            col(DataIngestionJob.state) == IngestionState.FINISHED,
            col(DataIngestionJob.result) != IngestionResult.ERROR,
            col(DataIngestionJob.is_current).is_(True),
            col(DataIngestionJob.ingestion_method) == IngestionMethod.csv,
        )
        rows = (await self.session.execute(stmt)).all()

        latest: Dict[int, int] = {}
        for job_id, module_type_id, det_id in rows:
            if job_id is None:
                continue
            covered: tuple[int, ...]
            if det_id is not None:
                covered = (det_id,)
            elif module_type_id is not None:
                try:
                    module = ModuleTypeEnum(module_type_id)
                except ValueError:
                    # Unknown module — skip rather than raise; operator can
                    # see the orphaned job via the existing jobs endpoints.
                    continue
                covered = tuple(
                    d.value for d in MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module, [])
                )
            else:
                # Both NULLs is meaningless for FACTORS scoping; skip.
                continue

            for det in covered:
                if latest.get(det, 0) < job_id:
                    latest[det] = job_id
        return latest

    async def list_stale_for_year(self, year: int) -> List[Factor]:
        """Return factors whose ``last_seen_job_id`` predates the latest
        successful FACTORS ingest job that covers their ``data_entry_type_id``
        in the given year.

        "Covers" handles two ingest shapes:

        - Per-det FACTORS job (``data_entry_type_id`` set) — covers exactly
          that det.
        - Multi-type FACTORS job (``data_entry_type_id`` NULL,
          ``module_type_id`` set) — covers every det in the module via
          ``MODULE_TYPE_TO_DATA_ENTRY_TYPES``.

        Operators use this to surface rows that exist in the DB but were
        not present in the most recent CSV upload.  Stale factors are not
        deleted (that would re-introduce dangling FKs), only flagged.

        Args:
            year: Restrict to factors and jobs in this year.
        """
        latest_per_det = await self._latest_factor_job_per_det(year)
        if not latest_per_det:
            # No is_current FACTORS job for this year → nothing to compare
            # against.  Returning all factors as "stale" would be misleading.
            return []

        # Per-det threshold: factor stale iff last_seen_job_id < latest[det].
        # CASE expression keeps the threshold lookup in SQL so we don't have
        # to fetch every factor row to filter in Python.
        threshold = case(
            *[
                (col(Factor.data_entry_type_id) == det, latest_id)
                for det, latest_id in latest_per_det.items()
            ],
            else_=None,
        )

        stmt = (
            select(Factor)
            .where(
                col(Factor.year) == year,
                col(Factor.data_entry_type_id).in_(latest_per_det.keys()),
                or_(
                    col(Factor.last_seen_job_id).is_(None),
                    col(Factor.last_seen_job_id) < threshold,
                ),
            )
            .order_by(col(Factor.data_entry_type_id), col(Factor.id))
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def update(self, factor_id: int, update_data: Dict) -> Optional[Factor]:
        """Update an existing factor."""
        factor = await self.get(factor_id)
        if not factor:
            return None

        for field, value in update_data.items():
            setattr(factor, field, value)

        await self.session.flush()
        await self.session.refresh(factor)
        return factor

    async def delete(self, factor_id: int) -> bool:
        """Delete a factor by ID."""
        factor = await self.get(factor_id)
        if not factor:
            return False

        await self.session.delete(factor)
        await self.session.flush()
        return True

    async def bulk_delete(self, factor_ids: list[int]) -> None:
        """Bulk delete factors by IDs."""
        stmt = select(Factor).where(col(Factor.id).in_(factor_ids))
        result = await self.session.exec(stmt)
        factors_to_delete = result.all()

        for factor in factors_to_delete:
            await self.session.delete(factor)

        await self.session.flush()

    async def list_id_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: Optional[int] = None,
    ) -> List[int]:
        """List all factors for a data entry type.

        Args:
            data_entry_type_id: Data entry type filter
            year: Optional year filter for year-scoped factors
        """
        conditions = [col(Factor.data_entry_type_id) == data_entry_type_id]

        # Add year filter if provided
        if year is not None:
            conditions.append(col(Factor.year) == year)

        stmt = select(Factor.id).where(*conditions)

        result = await self.session.exec(stmt)
        return [id for id in result.all() if id is not None]

    async def list_id_by_data_entry_type_and_year(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
    ) -> List[int]:
        """List factor IDs for data entry type and specific year.

        Args:
            data_entry_type_id: Data entry type filter
            year: Year filter (mandatory)
        """
        conditions = [
            col(Factor.data_entry_type_id) == data_entry_type_id.value,
            col(Factor.year) == year,
        ]

        stmt = select(Factor.id).where(*conditions)

        result = await self.session.exec(stmt)
        return [id for id in result.all() if id is not None]

    async def count_by_data_entry_type_and_year(
        self,
        data_entry_type_id: int,
        year: int,
    ) -> int:
        """Count factors for data entry type and specific year.

        Args:
            data_entry_type_id: Data entry type ID (int value)
            year: Year filter (mandatory)
        """
        conditions = [
            col(Factor.data_entry_type_id) == data_entry_type_id,
            col(Factor.year) == year,
        ]

        stmt = select(Factor.id).where(*conditions)

        result = await self.session.exec(stmt)
        return len(result.all())

    async def list_by_emission_type(
        self,
        emission_type: EmissionType,
        year: Optional[int] = None,
    ) -> List[Factor]:
        """List all factors for a given emission type.

        Args:
            emission_type: Emission type filter
            year: Optional year filter for year-scoped factors
        """
        conditions = [col(Factor.emission_type_id) == emission_type.value]

        # Add year filter if provided
        if year is not None:
            conditions.append(col(Factor.year) == year)

        stmt = select(Factor).where(*conditions)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: Optional[int] = None,
    ) -> List[Factor]:
        """List all factors for a data entry type.

        Args:
            data_entry_type_id: Data entry type filter
            year: Optional year filter for year-scoped factors
        """
        conditions = [col(Factor.data_entry_type_id) == data_entry_type_id]

        # Add year filter if provided
        if year is not None:
            conditions.append(col(Factor.year) == year)

        stmt = select(Factor).where(*conditions)

        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_class_subclass_map(
        self,
        data_entry_type: DataEntryTypeEnum,
        kind_field: str,
        subkind_field: str,
    ) -> Dict[str, List[str]]:
        """
        Return a mapping of equipment_class -> list of subclasses.

        Args:
            data_entry_type: The data entry type to filter on
            kind_field: Classification key for the primary class
            subkind_field: Classification key for the subclass
        """
        stmt = select(
            Factor.classification[kind_field].as_string(),
            Factor.classification[subkind_field].as_string(),
        ).where(col(Factor.data_entry_type_id) == data_entry_type.value)

        result = await self.session.exec(stmt)
        factors = result.all()

        mapping: Dict[str, List[str]] = {}

        for factor in factors:
            equipment_class = factor[0]
            sub_class = factor[1]

            if not equipment_class:
                continue

            if equipment_class not in mapping:
                mapping[equipment_class] = []

            if sub_class and sub_class not in mapping[equipment_class]:
                mapping[equipment_class].append(sub_class)

        # Sort subclasses
        for key in mapping:
            mapping[key].sort()

        return dict(sorted(mapping.items()))

    async def get_by_classification(
        self,
        data_entry_type: DataEntryTypeEnum,
        kind: str,
        subkind: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Optional[Factor]:
        """Get factor by classification with year filtering.

        Args:
            data_entry_type: Data entry type filter
            kind: Primary classification key
            subkind: Secondary classification key (optional)
            year: Year filter for year-scoped factors (should be provided)
        """
        # First try exact match with subkind
        handler = BaseModuleHandler.get_by_type(data_entry_type)
        kind_field = handler.kind_field or ""
        subkind_field = handler.subkind_field or ""

        if year is None:
            raise ValueError(
                "year is required for get_by_classification to avoid "
                "matching factors from multiple years"
            )

        conditions_base = [
            col(Factor.data_entry_type_id) == data_entry_type.value,
            col(Factor.year) == year,
        ]

        if subkind:
            conditions = conditions_base + [
                Factor.classification[kind_field].as_string() == kind,
                Factor.classification[subkind_field].as_string() == subkind,
            ]
            stmt = select(Factor).where(*conditions)
            result = await self.session.exec(stmt)
            factor = result.one_or_none()
            if factor:
                return factor

        # Fallback to kind-only match (no subkind)
        conditions = conditions_base + [
            Factor.classification[kind_field].as_string() == kind,
            Factor.classification[subkind_field].as_string().is_(None),
        ]
        stmt = select(Factor).where(*conditions)
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_factors(
        self,
        data_entry_type: DataEntryTypeEnum,
        fallbacks: Optional[dict[str, str]] = None,
        year: Optional[int] = None,
        **classification: str,
    ) -> List[Factor]:
        """Generic factor lookup with dynamic classification filters and year support.

        Args:
            data_entry_type: The data entry type to filter on
            fallbacks: Optional dict of fallback values for classification keys
                       e.g. {"country_code": "RoW"} to try RoW if exact match fails
            year: Year filter for year-scoped factors (should be provided)
            **classification: Classification filters (kind, subkind, category,
                              country_code, etc.)

        Examples:
            # Flight factor
            get_factors(DataEntryTypeEnum.trips, kind="plane", category="short_haul")

            # Train factor with RoW fallback
            get_factors(
                DataEntryTypeEnum.trips,
                fallbacks={"country_code": "RoW"},
                kind=TransportModeEnum.train.value,
                country_code="FR",
            )

        .. note:: Key remapping (kind → handler field name)

            Callers pass the *generic* keys ``kind`` / ``subkind`` because
            they don't know the handler's actual classification column names
            (e.g. ``building_name``, ``room_type``, ``equipment_class``).
            We remap those two keys to the handler's ``kind_field`` /
            ``subkind_field`` before building the SQL WHERE clause.

            This means the loop variable ``key`` is reassigned mid-iteration
            which is admittedly not the clearest pattern.  A cleaner approach
            would be to normalise ``classification`` into a new dict *before*
            building conditions, e.g.::

                resolved = {
                    (
                        kind_field
                        if k == "kind"
                        else subkind_field
                        if k == "subkind"
                        else k
                    ): v
                    for k, v in classification.items()
                    if v is not None
                }

            We keep the current inline style to stay consistent with
            ``get_by_classification`` and to minimise churn, but this note
            exists so the next person isn't surprised by the in-place rename.
        """
        handler = BaseModuleHandler.get_by_type(data_entry_type)
        kind_field = handler.kind_field or "kind"
        subkind_field = handler.subkind_field or "subkind"

        # Apply fallback values for None classification keys upfront so the
        # first query already includes them instead of producing an overly
        # broad WHERE clause that matches all factors for the data_entry_type.
        if fallbacks:
            for key, fallback_value in fallbacks.items():
                if key in classification and classification[key] is None:
                    classification[key] = fallback_value

        # Remap generic "kind"/"subkind" kwargs → handler-specific JSON keys.
        # e.g. kind="EPFL" becomes classification["building_name"] == "EPFL"
        # because BuildingRoomModuleHandler.kind_field == "building_name".
        # Keys that are *already* concrete (e.g. "country_code") pass through
        # unchanged.
        conditions = [col(Factor.data_entry_type_id) == data_entry_type.value]
        # Add year filter if provided
        if year is not None:
            conditions.append(col(Factor.year) == year)

        for key, value in classification.items():
            if value is None:
                continue
            if key == "kind":
                key = kind_field
            elif key == "subkind":
                key = subkind_field
            conditions.append(Factor.classification[key].as_string() == value)

        stmt = select(Factor).where(*conditions).order_by(col(Factor.id).asc())
        result = await self.session.exec(stmt)
        factors = result.all()

        if factors or not fallbacks:
            return [factor for factor in factors]

        # Try with remaining fallback values (for keys that had a non-None
        # original value that didn't match).
        for key, fallback_value in fallbacks.items():
            if key in classification:
                classification[key] = fallback_value

        # Rebuild conditions with fallback-replaced values (same remapping).
        conditions = [col(Factor.data_entry_type_id) == data_entry_type.value]
        # Add year filter if provided
        if year is not None:
            conditions.append(col(Factor.year) == year)

        for key, value in classification.items():
            if value is None:
                continue
            if key == "kind":
                key = kind_field
            elif key == "subkind":
                key = subkind_field
            conditions.append(Factor.classification[key].as_string() == value)

        stmt = select(Factor).where(*conditions).order_by(col(Factor.id).asc())
        result = await self.session.exec(stmt)
        return [factor for factor in result.all()]
