"""Provider that clones a data-entry-type's factors from a prior year.

Most factor tables (emission factor CSVs, unit costs, classifications) do
not change year over year — only a handful of rows get revised.  Rather
than forcing a full CSV/API/computed re-sync for every
``(module_type_id, data_entry_type_id)`` pair on every newly-opened year,
this provider copies the existing ``Factor`` rows for a source year
(default ``year - 1``, overridable via ``filters.source_year``) into the
target year.

Runs through the same ingestion-job pipeline as every other factor
provider (SSE progress, ``latest_factor_job`` enrichment, pipeline
observability) — see ``backend/app/services/data_ingestion/factor_update_provider.py``
for the sibling "computed" shape this mirrors.
"""

from typing import Any, Dict, List

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.factor_service import FactorService

logger = get_logger(__name__)


class FactorCopyProvider(DataIngestionProvider):
    """Clones ``Factor`` rows from a source year into the target year.

    Selects every factor for ``(data_entry_type_id, source_year)`` and
    writes a clone (``id=None``, ``year=target_year``) via
    ``FactorRepository.upsert_factors``.  That repository method's
    identity key — ``(data_entry_type_id, year, emission_type_id,
    classification::text)`` — excludes ``id``, so re-running this
    provider (a retry, or a deliberate re-copy) updates the existing
    target-year rows in place instead of duplicating them.

    No-ops cleanly (zero rows, ``SUCCESS`` result) when the source year
    has no factors for this data-entry type — nothing to copy is not an
    error.
    """

    @property
    def provider_name(self) -> IngestionMethod:
        """Return the ingestion method identifier."""
        return IngestionMethod.copy_previous_year

    @property
    def target_type(self) -> TargetType:
        """Return the target type for this provider."""
        return TargetType.FACTORS

    @property
    def entity_type(self) -> EntityType:
        """Return the entity type for this provider."""
        return EntityType.MODULE_PER_YEAR

    async def validate_connection(self) -> bool:
        """Always valid — no external connection required."""
        return True

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Not used; ingest is overridden directly."""
        return []

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Not used; ingest is overridden directly."""
        return raw_data

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Not used; ingest is overridden directly."""
        return {"inserted": 0, "skipped": 0, "errors": 0}

    def _resolve_source_year(
        self, target_year: int, filters: Dict[str, Any] | None
    ) -> int:
        """Resolve the source year: ``filters.source_year`` or ``year - 1``."""
        source_year_raw = (filters or {}).get("source_year")
        if source_year_raw is None:
            return target_year - 1
        return int(source_year_raw)

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Copy factors for ``(data_entry_type_id, source_year)`` into ``year``.

        Args:
            filters: Optional dict; ``source_year`` overrides the default
                     ``year - 1`` source.

        Returns:
            Dict with ``state``, ``status_message``, and ``data`` (stats dict).
        """
        await self._update_job(
            status_message="processing",
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata={"message": "Starting factor copy..."},
        )

        data_entry_type_id_raw = self.config.get("data_entry_type_id")
        year_raw = self.config.get("year")

        if data_entry_type_id_raw is None:
            raise ValueError("data_entry_type_id is required for factor copy")
        if year_raw is None:
            raise ValueError("year is required for factor copy")
        if self.job_id is None:
            raise ValueError("job_id is required for factor copy")

        target_year = int(year_raw)
        data_entry_type = DataEntryTypeEnum(int(data_entry_type_id_raw))
        source_year = self._resolve_source_year(target_year, filters)

        factor_service = FactorService(self.data_session)
        source_factors = await factor_service.list_by_data_entry_type(
            data_entry_type_id=data_entry_type,
            year=source_year,
        )

        stats: Dict[str, Any] = {
            "source_year": source_year,
            "target_year": target_year,
            "rows_found": len(source_factors),
            "rows_copied": 0,
        }

        if not source_factors:
            status_msg = (
                f"No factors found for {data_entry_type.name} in "
                f"{source_year}; nothing to copy"
            )
            await self._update_job(
                status_message=status_msg,
                state=IngestionState.FINISHED,
                result=IngestionResult.SUCCESS,
                extra_metadata={"message": status_msg, "stats": stats},
            )
            return {
                "state": IngestionState.FINISHED,
                "status_message": status_msg,
                "data": {"result": IngestionResult.SUCCESS, "stats": stats},
            }

        cloned: List[Factor] = [
            Factor(
                emission_type_id=factor.emission_type_id,
                data_entry_type_id=factor.data_entry_type_id,
                classification=factor.classification,
                values=factor.values,
                year=target_year,
            )
            for factor in source_factors
        ]

        factor_repo = FactorRepository(self.data_session)
        affected = await factor_repo.upsert_factors(cloned, current_job_id=self.job_id)
        # asyncpg can return rowcount=-1 for executemany ON CONFLICT
        # statements where it can't tally the result reliably — fall back
        # to the input size (mirrors ``BaseFactorCSVProvider._upsert_batch``).
        stats["rows_copied"] = affected if affected >= 0 else len(cloned)

        await self.data_session.flush()

        status_msg = (
            f"Copied {stats['rows_copied']} factor(s) from {source_year} "
            f"to {target_year}"
        )
        await self._update_job(
            status_message=status_msg,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            extra_metadata={"message": status_msg, "stats": stats},
        )

        return {
            "state": IngestionState.FINISHED,
            "status_message": status_msg,
            "data": {"result": IngestionResult.SUCCESS, "stats": stats},
        }
