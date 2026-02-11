import csv
import io
from abc import ABC, abstractmethod
from typing import Any, Dict, List, TypedDict

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionStatus,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.factor import FACTOR_META_FIELDS, BaseFactorHandler
from app.services.data_ingestion.base_csv_provider import (
    BATCH_SIZE,
    _validate_file_path,
)
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.factor_service import FactorService

logger = get_logger(__name__)


class FactorStatsDict(TypedDict):
    rows_processed: int
    rows_skipped: int
    batches_processed: int
    row_errors: list[dict[str, Any]]
    row_errors_count: int


def _get_expected_columns_from_handlers(handlers: list[Any]) -> set[str]:
    expected_columns: set[str] = set()
    for handler in handlers:
        expected_columns.update(handler.create_dto.model_fields.keys())
    meta_fields = set(FACTOR_META_FIELDS) | {"classification", "values"}
    return expected_columns - meta_fields


def _get_required_columns_from_handler(handler: Any) -> set[str]:
    meta_fields = set(FACTOR_META_FIELDS) | {"classification", "values"}
    return {
        name
        for name, field in handler.create_dto.model_fields.items()
        if field.is_required() and name not in meta_fields
    }


class BaseFactorCSVProvider(DataIngestionProvider, ABC):
    """Base class for CSV factor ingestion providers."""

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        data_session: Any = None,
    ):
        super().__init__(config, user, job_session, data_session)
        self.job_id = config.get("job_id")
        self.module_type_id = config.get("module_type_id")
        self.data_entry_type_id = config.get("data_entry_type_id")
        self.factor_variant = config.get("factor_variant")
        self.year = config.get("year")
        self.source_file_path = config.get("file_path")
        if self.source_file_path:
            _validate_file_path(self.source_file_path)
        self._files_store: Any = None
        self._repo: Any = None
        logger.info(
            f"Initializing {self.__class__.__name__} for job_id={self.job_id}, "
            f"file_path={self.source_file_path}"
        )

    @property
    def provider_name(self) -> IngestionMethod:
        return IngestionMethod.csv

    @property
    def target_type(self) -> TargetType:
        return TargetType.FACTORS

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

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return raw_data

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"inserted": 0, "skipped": 0, "errors": 0}

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            await self._update_job(
                status_message="processing",
                status_code=IngestionStatus.IN_PROGRESS,
                extra_metadata={"message": "Starting CSV processing..."},
            )
            result = await self.process_csv_in_batches()
            return {
                "status_code": IngestionStatus.COMPLETED,
                "status_message": "Success",
                "data": result,
            }
        except Exception as e:
            await self._update_job(
                status_message=f"failed: {str(e)}",
                status_code=IngestionStatus.FAILED,
                extra_metadata={"error": str(e)},
            )
            logger.error(f"CSV ingestion failed: {str(e)}")
            raise

    async def process_csv_in_batches(self) -> Dict[str, Any]:
        try:
            setup_result = await self._setup_and_validate()

            max_row_errors = int(self.config.get("max_row_errors", 100))
            stats: FactorStatsDict = {
                "rows_processed": 0,
                "rows_skipped": 0,
                "batches_processed": 0,
                "row_errors": [],
                "row_errors_count": 0,
            }
            factor_service = FactorService(self.data_session)

            batch: List[Factor] = []
            csv_reader = csv.DictReader(io.StringIO(setup_result["csv_text"]))

            for row_idx, row in enumerate(csv_reader, start=1):
                factor, error_msg = await self._process_row(
                    row,
                    row_idx,
                    setup_result,
                    stats,
                    max_row_errors,
                    factor_service,
                )

                if error_msg:
                    continue

                assert factor is not None
                batch.append(factor)
                stats["rows_processed"] += 1

                if len(batch) >= BATCH_SIZE:
                    await self._process_batch(batch, factor_service)
                    stats["batches_processed"] += 1
                    logger.info(
                        f"Processed batch {stats['batches_processed']}: "
                        f"{stats['rows_processed']} rows total"
                    )
                    batch = []

                    if stats["batches_processed"] % 5 == 0:
                        await self._update_job_and_sync(
                            repo=self.repo,
                            job_id=self.job_id,
                            status_message=f"Processing: {stats['rows_processed']}",
                            status_code=IngestionStatus.IN_PROGRESS,
                            metadata=dict(stats),
                        )
                        await self.data_session.flush()

            return await self._finalize_and_commit(
                batch, factor_service, stats, setup_result
            )
        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}", exc_info=True)
            await self.data_session.rollback()
            await self._update_job_and_sync(
                repo=self.repo,
                job_id=self.job_id,
                status_message=f"Processing failed: {str(e)}",
                status_code=IngestionStatus.FAILED,
                metadata={"error": str(e)},
            )
            raise

    async def _setup_and_validate(self) -> Dict[str, Any]:
        if self.year is None:
            raise ValueError("year is required for factor CSV ingestion")
        await self._update_job_and_sync(
            repo=self.repo,
            job_id=self.job_id,
            status_message="Starting CSV processing",
            status_code=IngestionStatus.IN_PROGRESS,
            metadata={},
        )
        await self.data_session.flush()

        tmp_path = self.source_file_path
        if not tmp_path:
            raise ValueError("Missing file_path in config")
        _validate_file_path(tmp_path)
        filename = tmp_path.split("/")[-1]
        processing_path = f"processing/{self.job_id}/{filename}"

        logger.info(f"Moving file from {tmp_path} to {processing_path}")
        move_result = await self.files_store.move_file(tmp_path, processing_path)
        if not move_result:
            raise ValueError("Failed to move file to processing path")

        logger.info(f"Downloading CSV from {processing_path}")
        file_content, mime_type = await self.files_store.get_file(processing_path)
        csv_text = file_content.decode("utf-8")

        entity_setup = await self._setup_handlers_and_context()
        handlers = entity_setup["handlers"]
        expected_columns = entity_setup["expected_columns"]
        required_columns = entity_setup["required_columns"]

        logger.info("Validating CSV headers")
        self._validate_csv_headers(csv_text, expected_columns, required_columns)

        return {
            "csv_text": csv_text,
            "handlers": handlers,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
            "processing_path": processing_path,
            "filename": filename,
            "valid_entry_types": entity_setup["valid_entry_types"],
            "factor_variant": entity_setup["factor_variant"],
        }

    def _validate_csv_headers(
        self,
        csv_text: str,
        expected_columns: set[str],
        required_columns: set[str],
    ) -> None:
        strict_mode = self.config.get("strict_column_validation", False)
        rows_to_check = 5

        validation_reader = csv.DictReader(io.StringIO(csv_text))
        first_rows = []

        try:
            for idx, row in enumerate(validation_reader):
                if idx >= rows_to_check:
                    break
                first_rows.append(row)
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {str(e)}")

        if not first_rows:
            raise ValueError("CSV file is empty")

        if required_columns:
            all_missing_required = all(
                not required_columns.issubset(set(row.keys())) for row in first_rows
            )

            if all_missing_required:
                missing_columns = required_columns - set(first_rows[0].keys())
                raise ValueError(
                    "CSV is missing required columns: "
                    f"{', '.join(sorted(missing_columns))}"
                )

        if strict_mode and expected_columns:
            all_missing_expected = all(
                not expected_columns.issubset(set(row.keys())) for row in first_rows
            )

            if all_missing_expected:
                missing_columns = expected_columns - set(first_rows[0].keys())
                raise ValueError(
                    "Strict mode: CSV is missing expected columns: "
                    f"{', '.join(sorted(missing_columns))}"
                )

    async def _process_row(
        self,
        row: Dict[str, str],
        row_idx: int,
        setup_result: Dict[str, Any],
        stats: FactorStatsDict,
        max_row_errors: int,
        factor_service: FactorService,
    ) -> tuple[Factor | None, str | None]:
        try:
            expected_columns = setup_result["expected_columns"]
            valid_entry_types = setup_result["valid_entry_types"]
            factor_variant = setup_result["factor_variant"]

            filtered_row = {
                k: v
                for k, v in row.items()
                if k in expected_columns and v is not None and str(v).strip() != ""
            }

            data_entry_type = self._resolve_data_entry_type(
                row, valid_entry_types, row_idx, stats, max_row_errors
            )
            if data_entry_type is None:
                return None, "Missing data_entry_type"

            variant = factor_variant
            if data_entry_type == DataEntryTypeEnum.trips:
                variant = variant or row.get("factor_variant")
                if not variant:
                    error_msg = "Missing factor_variant for travel factors"
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, error_msg

            handler = BaseFactorHandler.get_by_type(data_entry_type, variant)
            payload = dict(filtered_row)
            payload["data_entry_type_id"] = data_entry_type.value

            try:
                validated = handler.validate_create(payload)
            except Exception as validation_error:
                error_msg = f"Validation error: {validation_error}"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg

            classification = dict(validated.classification)
            if self.year is not None:
                classification["year"] = self.year

            factor = await factor_service.prepare_create(
                emission_type_id=validated.emission_type_id,
                is_conversion=validated.is_conversion,
                data_entry_type_id=validated.data_entry_type_id,
                classification=classification,
                values=validated.values,
            )
            return factor, None
        except Exception as row_error:
            logger.error(f"Row {row_idx}: Error processing row: {str(row_error)}")
            error_msg = f"Row processing error: {row_error}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg

    def _resolve_data_entry_type(
        self,
        row: Dict[str, str],
        valid_entry_types: list[DataEntryTypeEnum],
        row_idx: int,
        stats: FactorStatsDict,
        max_row_errors: int,
    ) -> DataEntryTypeEnum | None:
        configured = self.data_entry_type_id
        if configured is not None:
            return DataEntryTypeEnum(int(configured))

        raw_type_id = row.get("data_entry_type_id")
        raw_type_name = row.get("data_entry_type")

        if raw_type_id:
            try:
                return DataEntryTypeEnum(int(raw_type_id))
            except (ValueError, KeyError):
                error_msg = f"Invalid data_entry_type_id: {raw_type_id}"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None

        if raw_type_name:
            try:
                return DataEntryTypeEnum[str(raw_type_name).strip().lower()]
            except KeyError:
                error_msg = f"Invalid data_entry_type: {raw_type_name}"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None

        if len(valid_entry_types) == 1:
            return valid_entry_types[0]

        error_msg = "Missing data_entry_type in CSV"
        self._record_row_error(stats, row_idx, error_msg, max_row_errors)
        return None

    async def _process_batch(
        self,
        batch: List[Factor],
        factor_service: FactorService,
    ) -> None:
        await factor_service.bulk_create(batch)
        logger.info(f"Created {len(batch)} factors in batch")

    async def _finalize_and_commit(
        self,
        batch: List[Factor],
        factor_service: FactorService,
        stats: FactorStatsDict,
        setup_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if batch:
            await self._process_batch(batch, factor_service)

        processing_path = setup_result["processing_path"]
        filename = setup_result["filename"]
        processed_path = f"processed/{self.job_id}/{filename}"
        logger.info(f"Moving file from {processing_path} to {processed_path}")
        move_result = await self.files_store.move_file(processing_path, processed_path)
        if not move_result:
            raise ValueError("Failed to move file to processed path")

        await self.data_session.flush()

        await self._update_job_and_sync(
            repo=self.repo,
            job_id=self.job_id,
            status_message="CSV processing completed",
            status_code=IngestionStatus.COMPLETED,
            metadata=dict(stats),
        )

        return dict(stats)

    @abstractmethod
    async def _setup_handlers_and_context(self) -> Dict[str, Any]:
        pass

    @staticmethod
    def _record_row_error(
        stats: FactorStatsDict,
        row_idx: int,
        reason: str,
        max_row_errors: int,
    ) -> None:
        stats["rows_skipped"] += 1
        stats["row_errors_count"] += 1
        logger.warning(f"Row {row_idx}: {reason}")
        if len(stats["row_errors"]) < max_row_errors:
            stats["row_errors"].append({"row": row_idx, "reason": reason})

    def _resolve_valid_entry_types(self) -> list[DataEntryTypeEnum]:
        module_type_id = self.module_type_id
        if not module_type_id and self.job and self.job.module_type_id:
            module_type_id = self.job.module_type_id

        if module_type_id is None:
            raise ValueError("module_type_id is required for factor ingestion")

        module_type = ModuleTypeEnum(int(module_type_id))
        valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])
        if not valid_entry_types:
            raise ValueError(f"No data entry types for module type: {module_type}")
        return valid_entry_types
