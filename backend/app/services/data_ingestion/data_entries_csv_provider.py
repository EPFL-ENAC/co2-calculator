import csv
import io
from typing import Any, Dict, List, TypedDict

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionStatus,
    TargetType,
)
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.data_entry import (
    DATA_ENTRY_META_FIELDS,
    MODULE_HANDLERS,
    get_data_entry_handler_by_type,
)
from app.seed.seed_helper import is_in_factors_map, load_factors_map, lookup_factor
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider

logger = get_logger(__name__)

# Batch size for bulk inserts
BATCH_SIZE = 1000


class StatsDict(TypedDict):
    """Type definition for CSV processing statistics"""

    rows_processed: int
    rows_with_factors: int
    rows_without_factors: int
    rows_skipped: int
    batches_processed: int
    row_errors: list[dict[str, Any]]
    row_errors_count: int


def _get_expected_columns_from_handlers(handlers: list[Any]) -> set[str]:
    expected_columns: set[str] = set()
    for handler in handlers:
        expected_columns.update(handler.create_dto.model_fields.keys())
    return expected_columns


def _get_required_columns_from_handler(handler: Any) -> set[str]:
    meta_fields = set(DATA_ENTRY_META_FIELDS) | {"data"}
    return {
        name
        for name, field in handler.create_dto.model_fields.items()
        if field.is_required() and name not in meta_fields
    }


class DataEntriesCSVProvider(DataIngestionProvider):
    """Provider to ingest data entries from CSV files using handler-driven schemas"""

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
    ):
        super().__init__(config, user)
        # Extract job_id from config (will be set after create_job)
        self.job_id = config.get("job_id")
        # Extract carbon_report_module_id from config
        self.carbon_report_module_id = config.get(
            "carbon_report_module_id"
        ) or config.get("module_type_id")
        # Store the original file path from config
        self.source_file_path = config.get("file_path")
        # Lazy initialization - will be created when needed
        self._session: Any = None
        self._files_store: Any = None
        self._repo: Any = None
        logger.info(
            f"Initializing DataEntriesCSVProvider for job_id={self.job_id}, "
            f"file_path={self.source_file_path}"
        )

    @property
    def provider_name(self) -> IngestionMethod:
        return IngestionMethod.csv

    @property
    def target_type(self) -> TargetType:
        return TargetType.DATA_ENTRIES

    @property
    def session(self) -> Any:
        """Lazy initialization of database session"""
        if self._session is None:
            self._session = SessionLocal()
        return self._session

    @property
    def files_store(self) -> Any:
        """Lazy initialization of files store"""
        if self._files_store is None:
            from app.api.v1.files import make_files_store

            self._files_store = make_files_store()
        return self._files_store

    @property
    def repo(self) -> Any:
        """Lazy initialization of repository"""
        if self._repo is None:
            self._repo = DataIngestionRepository(self.session)
        return self._repo

    async def validate_connection(self) -> bool:
        """Validate that the CSV file exists at the source path"""
        logger.info("Validating connection for DataEntriesCSVProvider")
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
        """Not used - processing is done in process_csv_in_batches"""
        return []

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Not used - transformation is done in process_csv_in_batches"""
        return raw_data

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Not used - loading is done in process_csv_in_batches"""
        return {"inserted": 0, "skipped": 0, "errors": 0}

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Override ingest to use custom process_csv_in_batches"""
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
        """Process CSV file in batches with file movement and job status tracking"""
        try:
            # Update job status to PROCESSING
            await self.repo.update_ingestion_job(
                job_id=self.job_id,
                status_message="Starting CSV processing",
                status_code=IngestionStatus.IN_PROGRESS,
                metadata={},
            )

            # Move file from source path to processing/
            tmp_path = self.source_file_path
            # Extract filename from source path
            if not tmp_path:
                raise ValueError("Missing file_path in config")
            filename = tmp_path.split("/")[-1]
            processing_path = f"processing/{self.job_id}/{filename}"

            logger.info(f"Moving file from {tmp_path} to {processing_path}")
            move_result = await self.files_store.move_file(tmp_path, processing_path)
            if not move_result:
                raise Exception(
                    f"Failed to move file from {tmp_path} to {processing_path}"
                )

            # Download and decode CSV content
            logger.info(f"Downloading CSV from {processing_path}")
            file_content, mime_type = await self.files_store.get_file(processing_path)
            csv_text = file_content.decode("utf-8")

            entity_type_value = self.config.get("entity_type")
            if entity_type_value is None:
                entity_type = (
                    EntityType.MODULE_UNIT_SPECIFIC
                    if self.carbon_report_module_id
                    else EntityType.MODULE_PER_YEAR
                )
            else:
                entity_type = EntityType(entity_type_value)

            configured_data_entry_type_id = self.config.get("data_entry_type_id")

            # Load factors map
            logger.info("Loading factors map")
            factors_map: Dict[str, Any] = {}
            if entity_type == EntityType.MODULE_UNIT_SPECIFIC:
                if configured_data_entry_type_id is None:
                    raise Exception(
                        "data_entry_type must be specified for MODULE_UNIT_SPECIFIC"
                    )
                configured_data_entry_type = DataEntryTypeEnum(
                    configured_data_entry_type_id
                )
                type_factors = await load_factors_map(
                    self.session, configured_data_entry_type
                )
                factors_map.update(type_factors)
                handler = get_data_entry_handler_by_type(configured_data_entry_type)
                handlers = [handler]
                expected_columns = _get_expected_columns_from_handlers(handlers)
                required_columns = _get_required_columns_from_handler(handler)
            else:
                handlers = list(MODULE_HANDLERS.values())
                expected_columns = _get_expected_columns_from_handlers(handlers)
                required_columns = set()
                for entry_type in DataEntryTypeEnum:
                    type_factors = await load_factors_map(self.session, entry_type)
                    factors_map.update(type_factors)

            # Initialize statistics
            max_row_errors = int(self.config.get("max_row_errors", 100))
            stats: StatsDict = {
                "rows_processed": 0,
                "rows_with_factors": 0,
                "rows_without_factors": 0,
                "rows_skipped": 0,
                "batches_processed": 0,
                "row_errors": [],
                "row_errors_count": 0,
            }

            # Initialize services
            data_entry_service = DataEntryService(self.session)
            emission_service = DataEntryEmissionService(self.session)

            # Process CSV in batches
            batch: List[DataEntry] = []
            csv_reader = csv.DictReader(io.StringIO(csv_text))

            for row_idx, row in enumerate(csv_reader, start=1):
                try:
                    # Filter row to only include expected columns (discard extras)
                    filtered_row = {
                        k: v
                        for k, v in row.items()
                        if k in expected_columns and v is not None and v.strip() != ""
                    }

                    if (
                        entity_type == EntityType.MODULE_UNIT_SPECIFIC
                        and required_columns
                        and not required_columns.issubset(filtered_row.keys())
                    ):
                        missing_fields = required_columns - set(filtered_row.keys())
                        self._record_row_error(
                            stats,
                            row_idx,
                            f"Missing required fields {missing_fields}",
                            max_row_errors,
                        )
                        continue

                    factor = None
                    # TODO: verify that it works with EntityType.MODULE_YEAR
                    kind_value = (
                        filtered_row.get(handler.kind_field)
                        if handler.kind_field
                        else ""
                    )
                    subkind_value = (
                        filtered_row.get(handler.subkind_field)
                        if handler.subkind_field
                        else None
                    )
                    if kind_value:
                        factor = lookup_factor(
                            kind=kind_value,
                            subkind=subkind_value,
                            factors_map=factors_map,
                        )

                    if entity_type == EntityType.MODULE_PER_YEAR:
                        if not factor:
                            stats["rows_without_factors"] += 1
                            self._record_row_error(
                                stats,
                                row_idx,
                                "Missing factor for MODULE_PER_YEAR",
                                max_row_errors,
                            )
                            continue
                        data_entry_type = DataEntryTypeEnum(factor.data_entry_type_id)
                        handler = get_data_entry_handler_by_type(data_entry_type)
                    else:
                        if configured_data_entry_type_id is None:
                            raise Exception(
                                "data_entry_type must be specified for MODULE_UNIT"
                            )
                        data_entry_type = DataEntryTypeEnum(
                            configured_data_entry_type_id
                        )
                        match_factors = is_in_factors_map(
                            kind=filtered_row.get(handler.kind_field, ""),
                            subkind=filtered_row.get(handler.subkind_field, None),
                            factors_map=factors_map,
                            require_subkind=handler.require_subkind_for_factor,
                        )
                        if factor is None and match_factors is False:
                            # check is_in_factors_map
                            self._record_row_error(
                                stats,
                                row_idx,
                                "Probably not part of authorized data entries. "
                                "No matching factor found for kind/subkind",
                                max_row_errors,
                            )
                            continue
                        if (
                            factor
                            and factor.data_entry_type_id != data_entry_type.value
                        ):
                            self._record_row_error(
                                stats,
                                row_idx,
                                "Factor data_entry_type_id mismatch",
                                max_row_errors,
                            )
                            continue

                    if not self.carbon_report_module_id:
                        self._record_row_error(
                            stats,
                            row_idx,
                            "Missing carbon_report_module_id",
                            max_row_errors,
                        )
                        continue

                    payload = dict(filtered_row)
                    payload["data_entry_type_id"] = data_entry_type.value
                    payload["carbon_report_module_id"] = self.carbon_report_module_id

                    try:
                        validated = handler.validate_create(payload)
                    except Exception as validation_error:
                        self._record_row_error(
                            stats,
                            row_idx,
                            f"Validation error: {validation_error}",
                            max_row_errors,
                        )
                        continue

                    primary_factor_id = factor.id if factor else None
                    data = dict(validated.data)
                    data["primary_factor_id"] = primary_factor_id

                    if factor:
                        stats["rows_with_factors"] += 1
                    else:
                        stats["rows_without_factors"] += 1

                    data_entry = DataEntry(
                        data_entry_type_id=data_entry_type,
                        carbon_report_module_id=self.carbon_report_module_id,
                        data=data,
                    )
                    batch.append(data_entry)
                    stats["rows_processed"] += 1

                    # Process batch when it reaches BATCH_SIZE
                    if len(batch) >= BATCH_SIZE:
                        await self._process_batch(
                            batch, data_entry_service, emission_service
                        )
                        stats["batches_processed"] += 1
                        logger.info(
                            f"Processed batch {stats['batches_processed']}: "
                            f"{stats['rows_processed']} rows total"
                        )
                        batch = []  # Reset batch

                except Exception as row_error:
                    logger.error(
                        f"Row {row_idx}: Error processing row: {str(row_error)}"
                    )
                    self._record_row_error(
                        stats,
                        row_idx,
                        f"Row processing error: {row_error}",
                        max_row_errors,
                    )
                    continue

            # Process final batch (remaining rows < BATCH_SIZE)
            if batch:
                await self._process_batch(batch, data_entry_service, emission_service)
                stats["batches_processed"] += 1
                logger.info(
                    f"Processed final batch {stats['batches_processed']}: "
                    f"{stats['rows_processed']} rows total"
                )

            # Move file from processing/ to processed/
            processed_path = f"processed/{self.job_id}/{filename}"
            logger.info(f"Moving file from {processing_path} to {processed_path}")
            move_result = await self.files_store.move_file(
                processing_path, processed_path
            )
            if not move_result:
                logger.warning(
                    f"Failed to move file from {processing_path} to {processed_path}"
                )

            # Commit all changes
            await self.session.commit()
            logger.info(
                "All changes committed successfully",
                extra={"job_id": self.job_id, "length": stats["rows_processed"]},
            )

            # Update job status to COMPLETED with summary
            status_message = (
                f"Processed {stats['rows_processed']} rows: "
                f"{stats['rows_with_factors']} with factors, "
                f"{stats['rows_without_factors']} without factors, "
                f"{stats['rows_skipped']} skipped"
            )
            await self.repo.update_ingestion_job(
                job_id=self.job_id,
                status_message=status_message,
                status_code=IngestionStatus.COMPLETED,
                metadata=stats,
            )

            return {
                "status": "success",
                "inserted": stats["rows_processed"],
                "skipped": stats["rows_skipped"],
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}", exc_info=True)
            # Rollback session on error
            await self.session.rollback()

            # Update job status to FAILED
            await self.repo.update_ingestion_job(
                job_id=self.job_id,
                status_message=f"Processing failed: {str(e)}",
                status_code=IngestionStatus.FAILED,
                metadata={"error": str(e)},
            )
            raise

    async def _process_batch(
        self,
        batch: List[DataEntry],
        data_entry_service: DataEntryService,
        emission_service: DataEntryEmissionService,
    ) -> None:
        """Process a batch of data entries: bulk insert entries and emissions"""
        if not batch:
            return

        logger.info(f"Processing batch of {len(batch)} entries")

        # 1. Bulk create data entries
        data_entries_response = await data_entry_service.bulk_create(batch)

        # 2. Prepare emissions for all created data entries
        emissions_to_create = []
        for data_entry_response in data_entries_response:
            try:
                emission_obj = await emission_service.prepare_create(
                    data_entry_response
                )
                if emission_obj is not None:
                    emissions_to_create.append(emission_obj)
            except Exception as emission_error:
                logger.warning(
                    f"Failed to prepare emission for "
                    f"data_entry_id={data_entry_response.id}: "
                    f"{str(emission_error)}"
                )

        # 3. Bulk create emissions
        if emissions_to_create:
            await emission_service.bulk_create(emissions_to_create)
            logger.info(f"Created {len(emissions_to_create)} emissions for batch")

    @staticmethod
    def _record_row_error(
        stats: StatsDict,
        row_idx: int,
        reason: str,
        max_row_errors: int,
    ) -> None:
        stats["rows_skipped"] += 1
        stats["row_errors_count"] += 1
        logger.warning(f"Row {row_idx}: {reason}")
        if len(stats["row_errors"]) < max_row_errors:
            stats["row_errors"].append({"row": row_idx, "reason": reason})


EquipmentDataEntriesCSVProvider = DataEntriesCSVProvider
