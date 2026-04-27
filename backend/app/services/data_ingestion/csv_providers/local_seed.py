"""LocalFactorCSVProvider: runs factor CSV ingestion directly from local disk.

Used by seed scripts so they can reuse the full ingestion pipeline
(row validation, batch processing, emission-type resolution, error stats)
without requiring a running file-store service or DataIngestionJob records.
"""

from pathlib import Path
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionState
from app.services.data_ingestion.base_factor_csv_provider import FactorStatsDict
from app.services.data_ingestion.csv_providers.factors import (
    ModulePerYearFactorCSVProvider,
)

logger = get_logger(__name__)


class LocalFactorCSVProvider(ModulePerYearFactorCSVProvider):
    """Factor CSV provider that reads from local disk instead of the file store.

    Intended for seed scripts only. No DataIngestionJob records are created
    and no file-store operations (upload / move) are performed.

    Config keys
    -----------
    local_file_path : str
        Absolute path to the CSV file on disk.
    module_type_id : int
        Module type that owns the factors being seeded.
    data_entry_type_id : int | None
        Fixed data-entry type for single-type CSVs.  Pass None when the type
        is determined per-row via a category column.
    year : int
        Reference year for the seeded factors.
    explicit_entry_type_ids : list[int] | None
        When provided, deletion before seeding is scoped to exactly these
        DataEntryTypeEnum values.  Useful when a CSV covers only a subset of
        the module's types (e.g. purchases_common does not cover
        additional_purchases).
    """

    def __init__(self, config: Dict[str, Any], data_session: Any):
        # Pass job_session=None and user=None — no job tracking for seeds
        super().__init__(
            config=config,
            user=None,
            job_session=None,
            data_session=data_session,
        )
        self._local_file_path: str | None = config.get("local_file_path")
        raw_ids: list[int] | None = config.get("explicit_entry_type_ids")
        self._explicit_types: list[DataEntryTypeEnum] | None = (
            [DataEntryTypeEnum(i) for i in raw_ids] if raw_ids is not None else None
        )

    # ------------------------------------------------------------------
    # Override: validate against local filesystem, not file store
    # ------------------------------------------------------------------

    async def validate_connection(self) -> bool:
        if not self._local_file_path:
            logger.warning("No local_file_path provided")
            return False
        exists = Path(self._local_file_path).is_file()
        if not exists:
            logger.warning(f"Local CSV file not found: {self._local_file_path}")
        return exists

    # ------------------------------------------------------------------
    # Override: read directly from disk, skip file-store moves and DB job
    # ------------------------------------------------------------------

    async def _setup_and_validate(self) -> Dict[str, Any]:
        if self.year is None:
            raise ValueError("year is required for factor CSV ingestion")

        if not self._local_file_path:
            raise ValueError("Missing local_file_path in config")

        local_path = Path(self._local_file_path)
        if not local_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {self._local_file_path}")

        csv_text = local_path.read_text(encoding="utf-8")
        filename = local_path.name

        entity_setup = await self._setup_handlers_and_context()
        handlers = entity_setup["handlers"]
        expected_columns = entity_setup["expected_columns"]
        required_columns = entity_setup["required_columns"]

        logger.info("Validating CSV headers for local seed")
        self._validate_csv_headers(csv_text, expected_columns, required_columns)

        return {
            "csv_text": csv_text,
            "handlers": handlers,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
            # Dummy values — _finalize_and_commit checks these only for file-store
            "processing_path": None,
            "filename": filename,
            "valid_entry_types": entity_setup["valid_entry_types"],
        }

    # ------------------------------------------------------------------
    # Override: skip file-store moves and job DB updates after processing
    # ------------------------------------------------------------------

    async def _finalize_and_commit(
        self,
        batch: List[Any],
        factor_service: Any,
        stats: FactorStatsDict,
        setup_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if batch:
            await self._process_batch(batch, factor_service)

        await self.data_session.flush()

        result = self._compute_ingestion_result(stats)

        logger.info(
            f"Local seed completed: {stats['rows_processed']} rows processed, "
            f"{stats['rows_skipped']} skipped, "
            f"{stats['row_errors_count']} errors, "
            f"{stats['factors_deleted']} existing factors deleted"
        )
        return {
            "state": IngestionState.FINISHED,
            "result": result,
            "inserted": stats["rows_processed"],
            "skipped": stats["rows_skipped"],
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Override: respect explicit deletion scope set per FactorSeedConfig
    # ------------------------------------------------------------------

    def _get_types_to_delete(
        self, listed_entry_types: list[DataEntryTypeEnum]
    ) -> list[DataEntryTypeEnum]:
        if self._explicit_types is not None:
            return self._explicit_types
        return super()._get_types_to_delete(listed_entry_types)
