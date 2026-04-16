"""Base CSV provider for reduction-objective imports.

Each CSV is validated row-by-row with Pydantic, then the entire result is
stored as a JSON array inside ``year_configuration.config.reduction_objectives``.
"""

import csv
import io
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import User
from app.models.year_configuration import YearConfiguration
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.year_configuration import BaseReductionObjectiveHandler
from app.services.data_ingestion.base_csv_provider import _validate_file_path
from app.services.data_ingestion.base_provider import DataIngestionProvider

logger = get_logger(__name__)


class ReductionObjectiveStatsDict(TypedDict):
    rows_processed: int
    rows_skipped: int
    row_errors: list[dict[str, Any]]
    row_errors_count: int


class BaseReductionObjectiveCSVProvider(DataIngestionProvider, ABC):
    """Base class for reduction-objective CSV ingestion.

    Unlike factor/data-entry providers that create one DB row per CSV row,
    this provider collects all validated rows and writes them as a single
    JSON blob into ``year_configuration.config.reduction_objectives.<key>``.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        data_session: Any = None,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        self.job_id = config.get("job_id")
        self.year = config.get("year")
        raw_file_path = config.get("file_path")
        self.source_file_path = (
            urllib.parse.unquote(raw_file_path) if raw_file_path else None
        )
        if self.source_file_path:
            _validate_file_path(self.source_file_path)
        self._files_store: Any = None
        self._repo: Any = None
        logger.info(
            f"Initializing {self.__class__.__name__} for job_id={self.job_id}, "
            f"file_path={self.source_file_path}"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> IngestionMethod:
        return IngestionMethod.csv

    @property
    def target_type(self) -> TargetType:
        return TargetType.REDUCTION_OBJECTIVES

    @property
    @abstractmethod
    def entity_type(self) -> EntityType:
        pass

    @property
    def files_store(self) -> Any:
        if self._files_store is None:
            from app.api.v1.files import make_files_store

            self._files_store = make_files_store()
        return self._files_store

    @property
    def repo(self) -> Any:
        if self._repo is None:
            self._repo = DataIngestionRepository(self.data_session)
        return self._repo

    # ------------------------------------------------------------------
    # Abstract – subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _resolve_handler(self) -> BaseReductionObjectiveHandler:
        """Return the handler for the current upload (based on config)."""
        pass

    # ------------------------------------------------------------------
    # DataIngestionProvider abstract stubs (not used for this flow)
    # ------------------------------------------------------------------

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return raw_data

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"inserted": 0, "skipped": 0, "errors": 0}

    # ------------------------------------------------------------------
    # Connection validation
    # ------------------------------------------------------------------

    async def validate_connection(self) -> bool:
        logger.info(f"Validating connection for {self.__class__.__name__}")
        try:
            if not self.source_file_path:
                logger.warning("No file_path provided in config")
                return False
            exists = await self.files_store.file_exists(self.source_file_path)
            if exists:
                logger.info(
                    f"Successfully validated CSV file at {self.source_file_path}"
                )
                return True
            logger.warning(f"CSV file not found at {self.source_file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to validate CSV file: {str(e)}")
            return False

    # ------------------------------------------------------------------
    # Main ingestion flow
    # ------------------------------------------------------------------

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Override ingest to use the reduction-objective CSV flow."""
        try:
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Starting CSV processing..."},
            )
            result = await self._process_csv()
            return {
                "state": IngestionState.FINISHED,
                "status_message": "Success",
                "data": result,
            }
        except Exception as e:
            await self._update_job(
                status_message=f"failed: {str(e)}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(e)},
            )
            logger.error(f"Reduction-objective CSV ingestion failed: {str(e)}")
            raise

    async def _process_csv(self) -> Dict[str, Any]:
        """Setup → validate rows → store JSON → finalize."""
        try:
            setup = await self._setup_and_validate()
            handler: BaseReductionObjectiveHandler = setup["handler"]
            csv_text: str = setup["csv_text"]

            max_row_errors = int(self.config.get("max_row_errors", 100))
            stats: ReductionObjectiveStatsDict = {
                "rows_processed": 0,
                "rows_skipped": 0,
                "row_errors": [],
                "row_errors_count": 0,
            }

            # -- Parse & validate every row ---------------------------------
            validated_rows: list[dict] = []
            csv_reader = csv.DictReader(io.StringIO(csv_text, newline=""))

            for row_idx, raw_row in enumerate(csv_reader, start=1):
                # Strip whitespace from keys and values
                cleaned = {
                    k.strip(): v.strip() for k, v in raw_row.items() if k is not None
                }
                try:
                    validated = handler.validate_create(cleaned)
                    validated_rows.append(validated.model_dump())
                    stats["rows_processed"] += 1
                except Exception as e:
                    self._record_row_error(stats, row_idx, str(e), max_row_errors)

            if stats["rows_processed"] == 0:
                raise ValueError(
                    "No rows could be validated — check CSV format and content"
                )

            # -- Store in year_configuration --------------------------------
            await self._store_in_year_config(
                validated_rows=validated_rows,
                config_key=handler.config_key,
                filename=setup["filename"],
                processed_path=setup.get("processed_path"),
            )

            # -- Finalize ---------------------------------------------------
            return await self._finalize(stats, setup)

        except Exception as e:
            logger.error(
                f"Reduction-objective CSV processing failed: {str(e)}", exc_info=True
            )
            await self.data_session.rollback()
            await self._update_job(
                status_message=f"Processing failed: {str(e)}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(e)},
            )
            raise

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def _setup_and_validate(self) -> Dict[str, Any]:
        """Download CSV, move to processing/, resolve handler, validate headers."""
        if not self.job and self.job_id:
            self.job = await self.repo.get_job_by_id(self.job_id)
            if not self.job:
                raise ValueError(f"Job {self.job_id} not found")

        await self._update_job(
            status_message="Starting CSV processing",
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata={},
        )

        # Move file to processing/
        tmp_path = self.source_file_path
        if not tmp_path:
            raise ValueError("Missing file_path in config")
        _validate_file_path(tmp_path)
        filename = tmp_path.split("/")[-1]
        processing_path = f"processing/{self.job_id}/{filename}"

        logger.info(f"Moving file from {tmp_path} to {processing_path}")
        move_result = await self.files_store.move_file(tmp_path, processing_path)
        if not move_result:
            raise ValueError(
                f"Failed to move file from {tmp_path} to {processing_path}"
            )

        # Download & decode
        logger.info(f"Downloading CSV from {processing_path}")
        file_content, _ = await self.files_store.get_file(processing_path)
        csv_text = file_content.decode("utf-8-sig")

        # Resolve handler
        handler = self._resolve_handler()

        # Validate headers
        self._validate_csv_headers(
            csv_text, handler.expected_columns, handler.required_columns
        )

        processed_path = f"processed/{self.job_id}/{filename}"

        return {
            "csv_text": csv_text,
            "handler": handler,
            "processing_path": processing_path,
            "processed_path": processed_path,
            "filename": filename,
        }

    # ------------------------------------------------------------------
    # Header validation (same logic as BaseFactorCSVProvider)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_csv_headers(
        csv_text: str,
        expected_columns: set[str],
        required_columns: set[str],
    ) -> None:
        reader = csv.DictReader(io.StringIO(csv_text, newline=""))
        first_rows: list[dict] = []
        try:
            for idx, row in enumerate(reader):
                if idx >= 5:
                    break
                first_rows.append(row)
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {str(e)}")

        if not first_rows:
            raise ValueError("CSV file is empty")

        if required_columns:
            all_missing = all(
                not required_columns.issubset(set(row.keys())) for row in first_rows
            )
            if all_missing:
                missing = required_columns - set(first_rows[0].keys())
                raise ValueError(
                    f"CSV is missing required columns: {', '.join(sorted(missing))}"
                )

    # ------------------------------------------------------------------
    # Store validated rows into year_configuration.config
    # ------------------------------------------------------------------

    async def _store_in_year_config(
        self,
        validated_rows: list[dict],
        config_key: str,
        filename: str,
        processed_path: str | None = None,
    ) -> None:
        """Write the validated CSV rows into year_configuration.config."""
        if not self.year:
            raise ValueError("year is required")

        stmt = select(YearConfiguration).where(col(YearConfiguration.year) == self.year)
        result = (await self.data_session.exec(stmt)).first()
        if not result:
            raise ValueError(
                f"No year_configuration found for year {self.year}. Create it first."
            )

        # Ensure reduction_objectives structure exists
        if "reduction_objectives" not in result.config:
            result.config["reduction_objectives"] = {
                "files": {
                    "institutional_footprint": None,
                    "population_projections": None,
                    "unit_scenarios": None,
                },
                "institutional_footprint": None,
                "population_projections": None,
                "unit_scenarios": None,
                "goals": [],
            }
        else:
            ro = result.config["reduction_objectives"]
            for key in (
                "institutional_footprint",
                "population_projections",
                "unit_scenarios",
            ):
                ro.setdefault(key, None)
            ro.setdefault(
                "files",
                {
                    "institutional_footprint": None,
                    "population_projections": None,
                    "unit_scenarios": None,
                },
            )

        # Store parsed rows
        result.config["reduction_objectives"][config_key] = validated_rows

        # Store file metadata
        result.config["reduction_objectives"]["files"][config_key] = {
            "path": processed_path or "",
            "filename": filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        # SQLAlchemy does not detect in-place mutations on JSON/dict columns.
        # A shallow copy (e.g. `result.config = {**result.config}`) is unreliable
        # because the identity of nested objects may not change.
        # `flag_modified` explicitly marks the attribute as dirty so the
        # unit-of-work includes it in the next flush/commit.
        # See: https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.attributes.flag_modified
        flag_modified(result, "config")
        self.data_session.add(result)
        await self.data_session.flush()

        logger.info(
            f"Stored {len(validated_rows)} rows in "
            f"year_configuration.config.reduction_objectives.{config_key} "
            f"for year={self.year}"
        )

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    async def _finalize(
        self,
        stats: ReductionObjectiveStatsDict,
        setup: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Move file to processed/, update job to FINISHED."""
        processing_path = setup["processing_path"]
        processed_path = setup["processed_path"]

        logger.info(f"Moving file from {processing_path} to {processed_path}")
        move_result = await self.files_store.move_file(processing_path, processed_path)
        if not move_result:
            logger.warning(
                f"Failed to move file from {processing_path} to {processed_path}"
            )

        await self.data_session.flush()

        # Compute result
        result = self._compute_ingestion_result(stats)
        status_message = (
            f"Processed {stats['rows_processed']} rows, {stats['rows_skipped']} skipped"
        )
        await self._update_job(
            status_message=status_message,
            state=IngestionState.FINISHED,
            result=result,
            extra_metadata=dict(stats),
        )

        return {
            "state": IngestionState.FINISHED,
            "result": result,
            "rows_processed": stats["rows_processed"],
            "rows_skipped": stats["rows_skipped"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_ingestion_result(
        stats: ReductionObjectiveStatsDict,
    ) -> IngestionResult:
        if stats["rows_processed"] == 0:
            return IngestionResult.ERROR
        if stats["rows_skipped"] == 0:
            return IngestionResult.SUCCESS
        return IngestionResult.WARNING

    @staticmethod
    def _record_row_error(
        stats: ReductionObjectiveStatsDict,
        row_idx: int,
        reason: str,
        max_row_errors: int,
    ) -> None:
        stats["rows_skipped"] += 1
        stats["row_errors_count"] += 1
        logger.warning(f"Row {row_idx}: {reason}")
        if len(stats["row_errors"]) < max_row_errors:
            stats["row_errors"].append({"row": row_idx, "reason": reason})
