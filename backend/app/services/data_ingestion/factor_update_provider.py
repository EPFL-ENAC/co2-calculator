"""Abstract base provider for recomputing factor values from existing emissions."""

from abc import abstractmethod
from typing import Any, Dict, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

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

logger = get_logger(__name__)


class BaseFactorUpdateProvider(DataIngestionProvider):
    """Abstract provider that recomputes factor values from existing emission data.

    Subclasses implement ``compute_factor_values`` with the source-specific
    aggregation logic. The ``ingest`` loop handles retrieval, updates, stats
    tracking, and job-status reporting uniformly.
    """

    @property
    def provider_name(self) -> IngestionMethod:
        """Return the ingestion method identifier."""
        return IngestionMethod.computed

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

    async def fetch_data(self, filters: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Not used; ingest is overridden directly."""
        return []

    async def transform_data(
        self, raw_data: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        """Not used; ingest is overridden directly."""
        return raw_data

    async def _load_data(self, data: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Not used; ingest is overridden directly."""
        return {"inserted": 0, "skipped": 0, "errors": 0}

    @abstractmethod
    async def compute_factor_values(
        self,
        factor: Factor,
        year: int,
        session: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """Compute an updated values dict for a single factor.

        Args:
            factor: The factor record to update.
            year: The reference year for emission data.
            session: Database session (read-only inside this call; writes are
                     batched by the caller).

        Returns:
            A partial values dict whose keys will be merged into ``factor.values``
            (existing keys not present here are preserved). Return ``None`` to
            skip this factor without counting it as an error.

        Raises:
            ValueError: For hard errors such as a missing Unit or CarbonReport
                        that must be surfaced clearly.
        """

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Walk all factors for (data_entry_type_id, year) and recompute values.

        For each factor, calls ``compute_factor_values`` and merges the result
        into the existing factor.values (only the returned keys are overwritten;
        shares, use_unit, and total_use are left untouched unless explicitly
        returned).

        Args:
            filters: Unused; kept for interface compatibility.

        Returns:
            Dict with ``state``, ``status_message``, and ``data`` (stats dict).
        """
        await self._update_job(
            status_message="processing",
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata={"message": "Starting factor values recomputation..."},
        )

        data_entry_type_id_raw = self.config.get("data_entry_type_id")
        year_raw = self.config.get("year")

        if data_entry_type_id_raw is None:
            raise ValueError("data_entry_type_id is required for factor update")
        if year_raw is None:
            raise ValueError("year is required for factor update")

        year = int(year_raw)
        data_entry_type = DataEntryTypeEnum(int(data_entry_type_id_raw))

        factor_repo = FactorRepository(self.data_session)
        factors = await factor_repo.list_by_data_entry_type(
            data_entry_type_id=data_entry_type,
            year=year,
        )

        await self._update_job(
            status_message="processing",
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata={"message": f"Found {len(factors)} factors to process"},
        )

        stats: Dict[str, Any] = {
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
        }

        for factor in factors:
            if factor.id is None:
                stats["skipped"] += 1
                continue
            try:
                updated_values = await self.compute_factor_values(
                    factor, year, self.data_session
                )
                if updated_values is None:
                    stats["skipped"] += 1
                    continue

                # Merge: only overwrite the returned keys; preserve all others
                merged_values = {**factor.values, **updated_values}
                await factor_repo.update(factor.id, {"values": merged_values})
                stats["updated"] += 1

            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append({"factor_id": factor.id, "error": str(e)})
                logger.error(f"Error updating factor {factor.id}: {e}")

        result_outcome = (
            IngestionResult.WARNING if stats["errors"] > 0 else IngestionResult.SUCCESS
        )
        status_msg = (
            f"Completed with {stats['errors']} error(s)"
            if stats["errors"] > 0
            else "Success"
        )
        return {
            "state": IngestionState.FINISHED,
            "status_message": status_msg,
            "data": {
                "result": result_outcome,
                "stats": stats,
            },
        }
