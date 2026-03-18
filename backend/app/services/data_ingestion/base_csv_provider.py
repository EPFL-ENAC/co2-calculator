import csv
import io
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict

from app.core.logging import get_logger
from app.models.data_entry import (
    DataEntry,
    DataEntrySourceEnum,
    DataEntryStatusEnum,
    DataEntryTypeEnum,
)
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.data_entry import DATA_ENTRY_META_FIELDS, ModuleHandler
from app.schemas.user import UserRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.module_handler_service import ModuleHandlerService
from app.services.unit_service import UnitService
from app.services.user_service import UserService

logger = get_logger(__name__)

# Batch size for bulk inserts
BATCH_SIZE = 1000


def _validate_file_path(file_path: str) -> None:
    """
    Validate file_path to prevent directory traversal attacks.
    File should come from files_store and start with expected prefixes.
    """
    if not file_path:
        raise ValueError("file_path cannot be empty")

    # Prevent directory traversal
    if ".." in file_path:
        raise ValueError("Invalid file_path: directory traversal not allowed")

    # Normalize path and check for absolute paths
    if file_path.startswith("/"):
        raise ValueError("Invalid file_path: absolute paths not allowed")

    # Only allow files from tmp/ or similar temporary upload directories
    allowed_prefixes = ("tmp/", "uploads/", "temporary/")
    if not any(file_path.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(
            f"Invalid file_path: must start with one of {allowed_prefixes}"
        )


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


class BaseCSVProvider(DataIngestionProvider, ABC):
    """Base class for CSV data ingestion providers"""

    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        *,
        data_session: Any,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        # Extract job_id from config (will be set after create_job)
        self.job_id = config.get("job_id")
        # Extract carbon_report_module_id from config
        self.carbon_report_module_id = config.get("carbon_report_module_id")
        self.module_type_id = config.get("module_type_id")
        self.year = config.get("year")
        # Store the original file path from config
        raw_file_path = config.get("file_path")
        self.source_file_path = (
            urllib.parse.unquote(raw_file_path) if raw_file_path else None
        )
        if self.source_file_path:
            _validate_file_path(self.source_file_path)
        # Lazy initialization - will be created when needed
        self._files_store: Any = None
        self._repo: Any = None
        self._unit_service: Any = None
        self._user_service: Any = None
        # Track missing unit codes to skip rows during processing
        self._missing_unit_codes: set[str] = set()
        logger.info(
            f"Initializing {self.__class__.__name__} for job_id={self.job_id}, "
            f"file_path={self.source_file_path}"
        )

    @property
    def provider_name(self) -> IngestionMethod:
        return IngestionMethod.csv

    @property
    def target_type(self) -> TargetType:
        return TargetType.DATA_ENTRIES

    @property
    @abstractmethod
    def entity_type(self) -> EntityType:
        """Return the entity type for this provider"""
        pass

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
            self._repo = DataIngestionRepository(self.data_session)
        return self._repo

    @property
    def unit_service(self) -> UnitService:
        """Lazy initialization of unit service"""
        if self._unit_service is None:
            self._unit_service = UnitService(self.data_session)
        return self._unit_service

    @property
    def user_service(self) -> Any:
        """Lazy initialization of user service"""

        if self._user_service is None:
            self._user_service = UserService(self.data_session)
        return self._user_service

    async def validate_connection(self) -> bool:
        """Validate that the CSV file exists at the source path"""
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

    async def _validate_csv_headers(
        self,
        csv_text: str,
        expected_columns: set[str],
        required_columns: set[str],
    ) -> None:
        """
        Validate CSV headers by checking first 5 rows.
        Fails if ALL first rows are missing required columns.
        In strict mode, also fails if expected columns are missing.

        Raises ValueError if validation fails.
        """
        strict_mode = self.config.get("strict_column_validation", False)
        rows_to_check = 5

        # Validate using a separate reader
        validation_reader = csv.DictReader(io.StringIO(csv_text, newline=""))
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

        # Check required columns: fail if ALL first rows are missing them
        if required_columns:
            all_missing_required = all(
                not required_columns.issubset(set(row.keys())) for row in first_rows
            )

            if all_missing_required:
                missing_columns = required_columns - set(first_rows[0].keys())
                raise ValueError(
                    f"""CSV is missing required columns:
                    {", ".join(sorted(missing_columns))}"""
                )

        # In strict mode: fail if ALL first rows are missing any expected columns
        if strict_mode and expected_columns:
            all_missing_expected = all(
                not expected_columns.issubset(set(row.keys())) for row in first_rows
            )

            if all_missing_expected:
                missing_columns = expected_columns - set(first_rows[0].keys())
                raise ValueError(
                    f"""Strict mode: CSV is missing expected columns:
                        {", ".join(sorted(missing_columns))}"""
                )

    @abstractmethod
    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """
        Setup handlers and factors for this entity type.

        Subclasses should determine which handlers to load and which factors
        to retrieve, based on entity-specific configuration.

        Returns dict with keys:
            - handlers: list of handler instances
            - factors_map: dict of factors by classification
            - expected_columns: set of expected CSV columns
            - required_columns: set of required CSV columns
        """
        pass

    @abstractmethod
    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """
        Extract kind and subkind values from filtered row.

        Subclasses implement entity-specific extraction logic
        (e.g., single handler vs. multiple handlers).

        Returns: (kind_value, subkind_value)
        """
        pass

    @abstractmethod
    async def _resolve_handler_and_validate(
        self,
        filtered_row: Dict[str, str],
        factor: Any | None,
        stats: StatsDict,
        row_idx: int,
        max_row_errors: int,
        setup_result: Dict[str, Any],
    ) -> tuple[DataEntryTypeEnum | None, "ModuleHandler | None", str | None]:
        """
        Resolve the handler and validate the row.

        Subclasses implement entity-specific validation and handler resolution.

        Returns: (data_entry_type, handler, error_msg)
        If error_msg is not None, validation failed.
        """
        pass

    async def _resolve_carbon_report_modules(self, csv_text: str) -> Dict[str, int]:
        """
        Pre-scan CSV to extract unique unit_ids (institutional_ids)
        and resolve carbon_report_module_id.

        Note: CSV column is named 'unit_institutional_id'

        For each unique institutional_id:
        - Check if carbon_report exists for (unit_id, year)
        - Create report if missing (auto-creates all 7 modules)
        - Extract carbon_report_module_id for self.module_type_id

        Returns: {institutional_id: carbon_report_module_id} mapping
        """

        # Validate year is present
        if not self.year:
            raise ValueError("year is required for MODULE_PER_YEAR entity type")

        module_type_id = self.module_type_id
        if not module_type_id and self.job and self.job.module_type_id:
            module_type_id = self.job.module_type_id

        if not module_type_id:
            raise ValueError("module_type_id is required for MODULE_PER_YEAR")

        # Extract unique unit institutional_ids from CSV
        # (column is named 'unit_institutional_id' to be explicit)
        csv_reader = csv.DictReader(io.StringIO(csv_text, newline=""))
        unit_codes = set()
        for row in csv_reader:
            unit_code = row.get("unit_institutional_id")
            if unit_code and unit_code.strip():
                unit_codes.add(unit_code.strip())

        if not unit_codes:
            raise ValueError(
                "No valid unit_institutional_id values found in CSV. "
                "unit_id column is required for MODULE_PER_YEAR imports."
            )

        logger.info(
            f"Found {len(unit_codes)} unique unit institutional_ids in CSV: "
            f"{sorted(unit_codes)}"
        )

        # Validate unit institutional_ids exist to avoid FK violations
        unit_repo = UnitRepository(self.data_session)
        existing_units = await unit_repo.get_by_institutional_ids(list(unit_codes))
        existing_codes = {unit.institutional_id for unit in existing_units}
        missing_codes = sorted(unit_codes - existing_codes)
        if missing_codes:
            # Attempt to fetch and upsert missing units from provider
            logger.info(
                f"Found {len(missing_codes)} missing units in database, "
                f"attempting to fetch from provider"
            )

        # Build mapping of institutional_id to unit.id for DB operations
        # Only include units that exist (skip missing ones)
        unit_code_to_id = {unit.institutional_id: unit.id for unit in existing_units}

        # Resolve carbon_report_module_id for each institutional_id
        # Skip units that are missing
        carbon_report_service = CarbonReportService(self.data_session)
        code_to_module_map: Dict[str, int] = {}
        reports_created = 0
        reports_reused = 0

        for unit_institutional_id in unit_codes:
            # Skip missing units - they will be handled during row processing
            if unit_institutional_id in self._missing_unit_codes:
                continue

            # Get the database ID for this institutional_id
            unit_id = unit_code_to_id.get(unit_institutional_id)
            if not unit_id:
                logger.warning(
                    f"Unit with institutional_id={unit_institutional_id} not found"
                )
                # TODO: fix accred?
                continue

            # Check if carbon report exists
            carbon_report = await carbon_report_service.get_by_unit_and_year(
                unit_id, self.year
            )

            if not carbon_report:
                # Create new carbon report (auto-creates all 7 modules)
                logger.info(
                    "Creating carbon_report for "
                    f"institutional_id={unit_institutional_id} "
                    f"(unit_id={unit_id}), year={self.year}"
                )
                carbon_report = await carbon_report_service.create(
                    CarbonReportCreate(unit_id=unit_id, year=self.year)
                )
                reports_created += 1
            else:
                reports_reused += 1

            # Get the carbon_report_module_id for this module_type
            module_service = carbon_report_service.module_service
            carbon_report_module = await module_service.get_module(
                carbon_report.id, module_type_id
            )

            if not carbon_report_module:
                raise ValueError(
                    f"No carbon_report_module found for "
                    f"carbon_report_id={carbon_report.id}, "
                    f"module_type_id={module_type_id}"
                )

            # Map institutional_id (from CSV) to carbon_report_module_id
            code_to_module_map[unit_institutional_id] = carbon_report_module.id

        logger.info(
            f"Resolved carbon_report_module_ids: "
            f"created {reports_created} new reports, "
            f"reused {reports_reused} existing reports"
        )

        return code_to_module_map

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Override ingest to use custom process_csv_in_batches"""
        try:
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Starting CSV processing..."},
            )
            result = await self.process_csv_in_batches()
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
            logger.error(f"CSV ingestion failed: {str(e)}")
            raise

    async def _delete_existing_entries_for_module_per_year(
        self,
        unit_to_module_map: Dict[str, int],
        stats: StatsDict,
        data_entry_service: DataEntryService,
    ) -> None:
        """
        Delete existing entries from previous CSV_MODULE_PER_YEAR uploads.

        This ensures that MODULE_PER_YEAR uploads replace only the data
        that was uploaded through the same mechanism, preserving manual
        entries and unit-specific uploads.

        Args:
            unit_to_module_map: Mapping of unit ID to module ID
            stats: Statistics dict to update
            data_entry_service: DataEntryService instance to use
        """

        user_read = UserRead.model_validate(self.user) if self.user else None

        deleted_count = 0
        # Get all unique data_entry_types that will be processed
        # We'll delete all CSV_MODULE_PER_YEAR entries for affected modules
        for unit_id, module_id in unit_to_module_map.items():
            # Delete entries for all data_entry_types that could be in this module
            # We need to get the valid types for this module
            if self.job and self.job.module_type_id:
                from app.models.module_type import (
                    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
                    ModuleTypeEnum,
                )

                module_type = ModuleTypeEnum(self.job.module_type_id)
                valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

                for data_entry_type in valid_entry_types:
                    try:
                        await data_entry_service.bulk_delete_by_source(
                            carbon_report_module_id=module_id,
                            data_entry_type_id=data_entry_type,
                            source=DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value,
                            user=user_read,
                        )
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete entries for module {module_id}, "
                            f"type {data_entry_type}: {e}"
                        )

        logger.info(f"Deleted {deleted_count} entry sets from previous CSV uploads")

    async def process_csv_in_batches(self) -> Dict[str, Any]:
        """Orchestrate CSV processing: setup → process rows → finalize"""
        try:
            # Setup: validate, load factors, move file
            setup_result = await self._setup_and_validate()

            # Resolve carbon_report_module_ids if needed (MODULE_PER_YEAR only)
            unit_to_module_map: Dict[str, int] | None = None

            # Initialize statistics early for deletion tracking
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

            # Initialize services early (needed for deletion)
            data_entry_service = DataEntryService(self.data_session)
            emission_service = DataEntryEmissionService(self.data_session)

            if (
                self.entity_type == EntityType.MODULE_PER_YEAR
                and not self.carbon_report_module_id
            ):
                logger.info(
                    "Resolving carbon_report_module_ids for MODULE_PER_YEAR import"
                )
                unit_to_module_map = await self._resolve_carbon_report_modules(
                    setup_result["csv_text"]
                )
                # Store for later use in _recompute_module_stats
                self._unit_to_module_map = unit_to_module_map
                await self.data_session.flush()  # Flush report/module creation

                # Delete existing entries from previous CSV_MODULE_PER_YEAR uploads
                logger.info(
                    "Deleting existing CSV_MODULE_PER_YEAR entries before re-import"
                )
                await self._delete_existing_entries_for_module_per_year(
                    unit_to_module_map, stats, data_entry_service
                )

            # Process CSV rows
            batch: List[DataEntry] = []
            # Track seen user_institutional_ids per module to catch intra-CSV duplicates
            seen_institutional_ids: Dict[int, set] = {}
            csv_reader = csv.DictReader(
                io.StringIO(setup_result["csv_text"], newline="")
            )

            for row_idx, row in enumerate(csv_reader, start=1):
                # Process single row, returns (data_entry, error_msg, factor)
                data_entry, error_msg, factor = await self._process_row(
                    row,
                    row_idx,
                    setup_result,
                    stats,
                    max_row_errors,
                    unit_to_module_map,
                )

                if error_msg:
                    # Row had errors, already recorded in stats
                    continue

                if data_entry is None:
                    raise ValueError("Data entry is None without error message")

                # Check institutional ID uniqueness for member entries
                if (
                    data_entry.data_entry_type_id == DataEntryTypeEnum.member
                    and data_entry.data
                    and data_entry.data.get("user_institutional_id")
                ):
                    uid = str(data_entry.data["user_institutional_id"])
                    module_id = data_entry.carbon_report_module_id
                    module_seen = seen_institutional_ids.setdefault(module_id, set())
                    if uid in module_seen:
                        error_msg = "DUPLICATE_INSTITUTIONAL_ID"
                        self._record_row_error(
                            stats, row_idx, error_msg, max_row_errors
                        )
                        continue
                    is_unique = await data_entry_service.check_institutional_id_unique(
                        carbon_report_module_id=module_id,
                        uid=uid,
                    )
                    if not is_unique:
                        error_msg = "DUPLICATE_INSTITUTIONAL_ID"
                        self._record_row_error(
                            stats, row_idx, error_msg, max_row_errors
                        )
                        continue
                    module_seen.add(uid)

                # Row processed successfully
                batch.append(data_entry)
                if factor:
                    stats["rows_with_factors"] += 1
                else:
                    stats["rows_without_factors"] += 1
                stats["rows_processed"] += 1

                # Process batch when it reaches BATCH_SIZE
                if len(batch) >= BATCH_SIZE:
                    await self._process_batch(
                        batch, data_entry_service, emission_service, self.user
                    )
                    stats["batches_processed"] += 1
                    logger.info(
                        f"Processed batch {stats['batches_processed']}: "
                        f"{stats['rows_processed']} rows total"
                    )
                    batch = []
                    # Update job progress every 5 batches
                    if stats["batches_processed"] % 5 == 0:
                        await self._update_job(
                            status_message=f"Processing: {stats['rows_processed']}",
                            state=IngestionState.RUNNING,
                            result=None,
                            extra_metadata=dict(stats),
                        )

            # Finalize: process remaining batch, move file, update job
            return await self._finalize_and_commit(
                batch, data_entry_service, emission_service, stats, setup_result
            )

        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}", exc_info=True)
            await self.data_session.rollback()
            await self._update_job(
                status_message=f"Processing failed: {str(e)}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(e)},
            )
            raise

    async def _setup_and_validate(
        self,
    ) -> Dict[str, Any]:
        """
        Setup phase: move file, download CSV, load factors, validate headers.
        Returns context dict with all data needed for row processing.
        """
        # Load job from database if not already loaded (needed for module_type_id, etc.)
        if not self.job and self.job_id:
            self.job = await self.repo.get_job_by_id(self.job_id)
            if not self.job:
                raise ValueError(f"Job {self.job_id} not found")

        # Update job status to PROCESSING
        await self._update_job(
            status_message="Starting CSV processing",
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata={},
        )

        # Move file from source path to processing/
        tmp_path = self.source_file_path
        if not tmp_path:
            raise ValueError("Missing file_path in config")
        _validate_file_path(tmp_path)  # Extra safety check
        filename = tmp_path.split("/")[-1]
        processing_path = f"processing/{self.job_id}/{filename}"

        logger.info(f"Moving file from {tmp_path} to {processing_path}")
        move_result = await self.files_store.move_file(tmp_path, processing_path)
        if not move_result:
            raise Exception(f"Failed to move file from {tmp_path} to {processing_path}")

        # Download and decode CSV content
        logger.info(f"Downloading CSV from {processing_path}")
        file_content, mime_type = await self.files_store.get_file(processing_path)
        csv_text = file_content.decode("utf-8-sig")

        # Load handlers and factors (entity-specific)
        logger.info(f"Loading handlers and factors for {self.__class__.__name__}")
        entity_setup = await self._setup_handlers_and_factors()
        handlers = entity_setup["handlers"]
        factors_map = entity_setup["factors_map"]
        expected_columns = entity_setup["expected_columns"]
        required_columns = entity_setup["required_columns"]

        # Validate CSV headers upfront
        logger.info("Validating CSV headers")
        try:
            await self._validate_csv_headers(
                csv_text, expected_columns, required_columns
            )
            logger.info("CSV header validation passed")
        except ValueError as validation_error:
            error_message = str(validation_error)
            logger.error(f"CSV validation failed: {error_message}")
            await self._update_job(
                status_message=f"Column validation failed: {error_message}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"validation_error": error_message},
            )
            raise

        return {
            "csv_text": csv_text,
            "entity_type": self.entity_type,
            "handlers": handlers,
            "factors_map": factors_map,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
            "processing_path": processing_path,
            "filename": filename,
        }

    async def _process_row(
        self,
        row: Dict[str, str],
        row_idx: int,
        setup_result: Dict[str, Any],
        stats: StatsDict,
        max_row_errors: int,
        unit_to_module_map: Dict[str, int] | None = None,
    ) -> tuple[DataEntry | None, str | None, Any | None]:
        """
        Process a single CSV row.
        Returns (DataEntry, error_msg, factor) tuple.
        If error_msg is not None, row processing failed and error was recorded.

        Args:
            unit_to_module_map: Optional mapping of institutional_id
                               to carbon_report_module_id
                               for MODULE_PER_YEAR imports
        """
        try:
            handlers = setup_result["handlers"]
            # factors_map = setup_result["factors_map"]
            expected_columns = setup_result["expected_columns"]
            # force kg_co2eq column in expected columns to allow flexibility
            # in handlers (some may not require it,
            # for module_year it is required for factor resolution,
            # but for module_unit_specific it is not needed and often not provided)
            # expected_columns.add("kg_co2eq")

            # Filter row to only include expected columns
            filtered_row = {
                k: v
                for k, v in row.items()
                if k in expected_columns and v is not None and v.strip() != ""
            }

            # Extract kind/subkind values (entity-specific extraction)
            kind_value, subkind_value = self._extract_kind_subkind_values(
                filtered_row, handlers
            )

            # Resolve handler and data_entry_type first (needed for factor lookup)
            (
                data_entry_type,
                handler,
                error_msg,
            ) = await self._resolve_handler_and_validate(
                filtered_row, None, stats, row_idx, max_row_errors, setup_result
            )

            if error_msg:
                return None, error_msg, None

            if not data_entry_type or not handler:
                error_msg = "Failed to resolve handler and data_entry_type"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None

            # Use ModuleHandlerService to resolve primary_factor_id (unified with API)
            handler_service = ModuleHandlerService(self.data_session)
            payload_for_factor_resolution: Dict[str, str | int] = dict(filtered_row)
            payload_with_factor = await handler_service.resolve_primary_factor_id(
                handler=handler,
                payload=payload_for_factor_resolution,
                data_entry_type_id=data_entry_type,
            )
            primary_factor_id = payload_with_factor.get("primary_factor_id")

            # Resolve carbon_report_module_id
            carbon_report_module_id = None

            if unit_to_module_map is not None:
                # MODULE_PER_YEAR: resolve from unit_institutional_id
                unit_institutional_id = row.get("unit_institutional_id")
                if (
                    unit_institutional_id is None
                    or str(unit_institutional_id).strip() == ""
                ):
                    error_msg = "Missing unit_institutional_id in row"
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, error_msg, None

                unit_institutional_id = str(unit_institutional_id).strip()

                # Skip rows with missing units
                if unit_institutional_id in self._missing_unit_codes:
                    error_msg = f"Unit '{unit_institutional_id}' not found"

                carbon_report_module_id = unit_to_module_map.get(unit_institutional_id)
                if not carbon_report_module_id:
                    error_msg = (
                        f"No carbon_report_module_id mapped for "
                        f"institutional_id={unit_institutional_id}"
                    )
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, error_msg, None
            elif self.carbon_report_module_id:
                # MODULE_UNIT_SPECIFIC: use pre-configured value
                carbon_report_module_id = self.carbon_report_module_id
            else:
                # Neither mapping nor pre-configured value available
                error_msg = "Missing carbon_report_module_id"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None

            # Validate payload with handler (primary_factor_id already
            # set by ModuleHandlerService)
            payload: Dict[str, str | int | None] = dict(filtered_row)
            payload["data_entry_type_id"] = data_entry_type.value
            payload["carbon_report_module_id"] = carbon_report_module_id
            payload["status"] = DataEntryStatusEnum.VALIDATED.value
            payload["primary_factor_id"] = primary_factor_id

            try:
                validated = handler.validate_create(payload)
            except Exception as validation_error:
                error_msg = f"Validation error: {validation_error}"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None

            # Build DataEntry
            data = dict(validated.data)

            # Note: primary_factor_id is already in payload and
            # will be in validated.data
            # No need to set it again

            # Populate missing data fields from factor values
            # (e.g., equipment usage hours, default quantities)
            # Only do this if we have a primary_factor_id and factors_map available
            if primary_factor_id and "factors_map" in setup_result:
                factors_map = setup_result["factors_map"]
                # Lookup factor by primary_factor_id
                factor = None
                # Could do better: factors_map is keyed by classification and
                # we have to loop through to find the factor with matching ID
                for factor_key, factor_obj in factors_map.items():
                    if getattr(factor_obj, "id", None) == primary_factor_id:
                        factor = factor_obj
                        break

                # Populate defaults from factor if handler defines factor_value_fields
                if (
                    factor
                    and hasattr(handler, "factor_value_fields")
                    and handler.factor_value_fields
                ):
                    for field_name in handler.factor_value_fields:
                        if field_name not in data or data[field_name] in (None, "", 0):
                            default_value = factor.values.get(field_name)
                            if default_value is not None:
                                data[field_name] = default_value
                                logger.debug(
                                    f"Row {row_idx}: Populated "
                                    f"{field_name}={default_value}"
                                    f"from factor"
                                )

            data_entry = DataEntry(
                data_entry_type_id=data_entry_type,
                carbon_report_module_id=carbon_report_module_id,
                data=data,
            )

            return data_entry, None, None

        except Exception as row_error:
            logger.error(f"Row {row_idx}: Error processing row: {str(row_error)}")
            error_msg = f"Row processing error: {row_error}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

    def _compute_ingestion_result(self, stats: StatsDict) -> IngestionResult:
        """
        Compute ingestion result based on success rate.

        Rules:
        - SUCCESS: rows_skipped == 0 (100% processed)
        - WARNING: rows_skipped > 0 and rows_processed > 0 (partial success)
        - ERROR: rows_processed == 0 (nothing processed)

        Args:
            stats: Statistics dict with rows_processed and rows_skipped

        Returns:
            IngestionResult enum value
        """
        rows_processed = stats["rows_processed"]
        rows_skipped = stats["rows_skipped"]

        if rows_processed == 0:
            return IngestionResult.ERROR  # Nothing processed at all

        if rows_skipped == 0:
            return IngestionResult.SUCCESS  # 100% success

        return IngestionResult.WARNING  # Partial success (some skipped)

    async def _finalize_and_commit(
        self,
        batch: List[DataEntry],
        data_entry_service: DataEntryService,
        emission_service: DataEntryEmissionService,
        stats: StatsDict,
        setup_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Finalize: process remaining batch, move file to processed/, update job.
        """
        # Process final batch (remaining rows < BATCH_SIZE)
        if batch:
            await self._process_batch(
                batch, data_entry_service, emission_service, self.user
            )
            stats["batches_processed"] += 1
            logger.info(
                f"Processed final batch {stats['batches_processed']}: "
                f"{stats['rows_processed']} rows total"
            )

        # Move file from processing/ to processed/
        processing_path = setup_result["processing_path"]
        filename = setup_result["filename"]
        processed_path = f"processed/{self.job_id}/{filename}"
        logger.info(f"Moving file from {processing_path} to {processed_path}")
        move_result = await self.files_store.move_file(processing_path, processed_path)
        if not move_result:
            logger.warning(
                f"Failed to move file from {processing_path} to {processed_path}"
            )

        # Flush all changes
        await self.data_session.flush()
        logger.info(
            "All changes flushed successfully",
            extra={"job_id": self.job_id, "length": stats["rows_processed"]},
        )

        # Recompute stats for affected carbon report modules
        await self._recompute_module_stats()

        # Update job status to COMPLETED with summary
        status_message = (
            f"Processed {stats['rows_processed']} rows: "
            f"{stats['rows_with_factors']} with factors, "
            f"{stats['rows_without_factors']} without factors, "
            f"{stats['rows_skipped']} skipped"
        )
        # Compute result dynamically based on success rate
        result = self._compute_ingestion_result(stats)

        # Prepare metadata: exclude row_errors from root level to avoid duplication
        # (row_errors remain in stats for detailed error reporting)
        metadata_for_job = {k: v for k, v in stats.items() if k != "row_errors"}
        # Add stats with row_errors for detailed reporting
        metadata_for_job["stats"] = stats

        await self._update_job(
            status_message=status_message,
            state=IngestionState.FINISHED,
            result=result,
            extra_metadata=metadata_for_job,
        )

        return {
            "state": IngestionState.FINISHED,
            "result": result,
            "inserted": stats["rows_processed"],
            "skipped": stats["rows_skipped"],
            "stats": stats,
        }

    async def _process_batch(
        self,
        batch: List[DataEntry],
        data_entry_service: DataEntryService,
        emission_service: DataEntryEmissionService,
        user: Optional[User],
    ) -> None:
        """Process a batch of data entries: bulk insert entries and emissions"""
        if not batch:
            return

        logger.info(f"Processing batch of {len(batch)} entries")

        # Determine source based on entity_type
        source = self._get_source_from_entity_type()

        # 1. Bulk create data entries with source tracking
        data_entries_response = await data_entry_service.bulk_create(
            batch,
            UserRead.model_validate(user) if user else None,
            job_id=self.job_id,
            source=source.value if source else None,
            created_by_id=self.job_id,
        )

        # 2. Prepare emissions for all created data entries
        emissions_to_create = []
        for data_entry_response in data_entries_response:
            try:
                emission_objs = await emission_service.prepare_create(
                    data_entry_response
                )
                if emission_objs is not None:
                    emissions_to_create.extend(emission_objs)
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

    async def _recompute_module_stats(self) -> None:
        """
        Recompute stats for all affected carbon report modules and parent reports.

        For MODULE_PER_YEAR: recomputes stats for each module in unit_to_module_map,
        then recomputes stats for each affected carbon report.
        For MODULE_UNIT_SPECIFIC: recomputes stats for self.carbon_report_module_id,
        then recomputes stats for the parent carbon report.
        """
        from app.services.carbon_report_service import CarbonReportService

        crm_service = CarbonReportModuleService(self.data_session)
        cr_service = CarbonReportService(self.data_session)
        module_ids_to_recompute: set[int] = set()
        carbon_report_ids_to_recompute: set[int] = set()

        # Collect module IDs and carbon report IDs based on entity type
        if self.entity_type == EntityType.MODULE_PER_YEAR:
            # Resolve carbon_report_module_ids if not already done
            if (
                not hasattr(self, "_unit_to_module_map")
                or self._unit_to_module_map is None
            ):
                logger.warning(
                    "unit_to_module_map not available for stats recomputation"
                )
                return
            module_ids_to_recompute = set(self._unit_to_module_map.values())
            # Extract unique carbon_report_ids from modules
            # Need to fetch modules to get their carbon_report_id
            for module_id in module_ids_to_recompute:
                module = await crm_service.repo.get(module_id)
                if module:
                    carbon_report_ids_to_recompute.add(module.carbon_report_id)
        elif self.entity_type == EntityType.MODULE_UNIT_SPECIFIC:
            if self.carbon_report_module_id:
                module_ids_to_recompute.add(self.carbon_report_module_id)
                # Get the carbon_report_id from the module
                module = await crm_service.repo.get(self.carbon_report_module_id)
                if module:
                    carbon_report_ids_to_recompute.add(module.carbon_report_id)
            else:
                logger.warning(
                    "carbon_report_module_id not set for MODULE_UNIT_SPECIFIC"
                )
                return

        # Recompute stats for each module
        for module_id in module_ids_to_recompute:
            try:
                await crm_service.recompute_stats(module_id)
                logger.info(f"Recomputed stats for carbon_report_module_id={module_id}")
            except Exception as stats_error:
                logger.error(
                    "Failed to recompute stats for carbon_report_module_id=%s: %s",
                    module_id,
                    stats_error,
                    exc_info=True,
                )

        # Recompute stats for each affected carbon report
        for carbon_report_id in carbon_report_ids_to_recompute:
            try:
                await cr_service.recompute_report_stats(carbon_report_id)
                logger.info(f"Recomputed stats for carbon_report_id={carbon_report_id}")
            except Exception as stats_error:
                logger.error(
                    "Failed to recompute stats for carbon_report_id=%s: %s",
                    carbon_report_id,
                    stats_error,
                    exc_info=True,
                )

    def _get_source_from_entity_type(self) -> DataEntrySourceEnum | None:
        """
        Determine source enum value based on entity_type.

        Returns:
            DataEntrySourceEnum value or None if not determinable
        """
        if self.entity_type == EntityType.MODULE_PER_YEAR:
            return DataEntrySourceEnum.CSV_MODULE_PER_YEAR
        elif self.entity_type == EntityType.MODULE_UNIT_SPECIFIC:
            return DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC
        return None

    @staticmethod
    def _resolve_data_entry_type_from_category(
        row: Dict[str, str],
        handler: Any,
        row_idx: int,
        stats: StatsDict,
        max_row_errors: int,
    ) -> DataEntryTypeEnum | None:
        """
        Resolve data_entry_type from module-specific category column.

        Args:
            row: CSV row data
            handler: Module handler with category_field defined
            row_idx: Current row index for error reporting
            stats: Stats dict for error tracking
            max_row_errors: Maximum errors to record

        Returns:
            DataEntryTypeEnum if resolved, None otherwise
        """
        category_field = getattr(handler, "category_field", None)

        if not category_field:
            # No category field defined for this handler
            return None

        category_value = row.get(category_field, "").strip()

        if not category_value:
            # Category field not present in this row
            return None

        try:
            # Map category string to DataEntryTypeEnum
            # e.g., "scientific" -> DataEntryTypeEnum.scientific
            data_entry_type = DataEntryTypeEnum[category_value.lower()]
            return data_entry_type
        except KeyError:
            error_msg = f"Invalid {category_field}: {category_value}"
            BaseCSVProvider._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None

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
