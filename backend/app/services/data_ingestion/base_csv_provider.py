import csv
import io
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_ingestion import (
    EntityType,
    IngestionMethod,
    IngestionStatus,
    TargetType,
)
from app.models.user import User
from app.providers.unit_provider import get_unit_provider
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.data_entry import ModuleHandler
from app.schemas.user import UserRead
from app.seed.seed_helper import lookup_factor
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider
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
    from app.schemas.data_entry import DATA_ENTRY_META_FIELDS

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
        self.source_file_path = config.get("file_path")
        if self.source_file_path:
            _validate_file_path(self.source_file_path)
        # Lazy initialization - will be created when needed
        self._files_store: Any = None
        self._repo: Any = None
        self._unit_service: Any = None
        self._user_service: Any = None
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

    async def _fetch_and_upsert_missing_units(
        self, missing_codes: list[str], batch_size: int = 100
    ) -> None:
        """
        Fetch missing units from provider and upsert them.

        Inspired by unit_sync_from_provider in user_service:
        - Validate user and provider are configured
        - Get unit provider based on user's provider type
        - Fetch units from provider in batches
        - Upsert each unit via unit_service.upsert()

        Args:
            missing_codes: List of unit provider_codes to fetch
            batch_size: Number of units to fetch per API call (default: 100)

        Raises:
            ValueError: If user or provider not configured
            Exception: If fetching units from provider fails
        """
        # Validate user and provider are configured
        job_user_provider = self.config.get("provider", None)
        if job_user_provider is None:
            raise ValueError(
                """job_user_provider: a.k.a. User Provider is required to
                    fetch missing units from provider"""
            )

        logger.info(
            f"Fetching {len(missing_codes)} missing units from provider",
            extra={"missing_codes": sorted(missing_codes), "batch_size": batch_size},
        )

        # Get unit provider based on user's provider type
        unit_provider = get_unit_provider(
            provider_type=job_user_provider, db_session=self.data_session
        )

        # Process units in batches
        units_fetched = 0
        units_upserted = 0

        for i in range(0, len(missing_codes), batch_size):
            batch = missing_codes[i : i + batch_size]
            logger.info(f"Fetching batch {i // batch_size + 1} ({len(batch)} units)")

            try:
                # Fetch units from provider (batch already contains string codes)
                fetched_units = await unit_provider.get_units(unit_ids=batch)
                units_fetched += len(fetched_units)

                # Upsert each unit
                for unit in fetched_units:
                    try:
                        if unit.principal_user_provider_code:
                            principal_user = await self.user_service.get_by_code(
                                unit.principal_user_provider_code
                            )
                            if not principal_user:
                                # Create minimal principal user if it doesn't exist
                                logger.info(
                                    "Creating minimal principal user record",
                                    extra={
                                        "provider_code": (
                                            unit.principal_user_provider_code
                                        )
                                    },
                                )
                                await self.user_service.upsert_user(
                                    id=None,
                                    provider_code=unit.principal_user_provider_code,
                                    email=f"{unit.principal_user_provider_code}@placeholder.local",
                                    provider=job_user_provider,
                                )

                        await self.unit_service.upsert(unit_data=unit)
                        units_upserted += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to upsert unit {unit.provider_code}",
                            extra={
                                "unit_provider_code": unit.provider_code,
                                "error": str(e),
                            },
                        )
                        raise

            except Exception as e:
                logger.error(
                    "Failed to fetch batch of units",
                    extra={
                        "batch": sorted(batch),
                        "error": str(e),
                        "type": type(e).__name__,
                    },
                )
                raise

        logger.info(
            "Fetched and upserted missing units",
            extra={
                "units_fetched": units_fetched,
                "units_upserted": units_upserted,
                "missing_count": len(missing_codes),
            },
        )

    async def _resolve_carbon_report_modules(self, csv_text: str) -> Dict[str, int]:
        """
        Pre-scan CSV to extract unique unit_ids (provider_codes)
        and resolve carbon_report_module_id.

        Note: CSV column is named 'unit_id' but contains provider_codes
        (strings), not DB IDs.

        For each unique provider_code:
        - Check if carbon_report exists for (unit_id, year)
        - Create report if missing (auto-creates all 7 modules)
        - Extract carbon_report_module_id for self.module_type_id

        Returns: {provider_code: carbon_report_module_id} mapping
        """
        from app.repositories.unit_repo import UnitRepository
        from app.schemas.carbon_report import CarbonReportCreate
        from app.services.carbon_report_service import CarbonReportService

        # Validate year is present
        if not self.year:
            raise ValueError("year is required for MODULE_PER_YEAR entity type")

        module_type_id = self.module_type_id
        if not module_type_id and self.job and self.job.module_type_id:
            module_type_id = self.job.module_type_id

        if not module_type_id:
            raise ValueError("module_type_id is required for MODULE_PER_YEAR")

        # Extract unique unit provider_codes from CSV (column is named 'unit_id')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        unit_codes = set()
        for row in csv_reader:
            unit_code = row.get("unit_id")
            if unit_code and unit_code.strip():
                unit_codes.add(unit_code.strip())

        if not unit_codes:
            raise ValueError(
                "No valid unit_id values found in CSV. "
                "unit_id column is required for MODULE_PER_YEAR imports."
            )

        logger.info(
            f"Found {len(unit_codes)} unique unit provider_codes in CSV: "
            f"{sorted(unit_codes)}"
        )

        # Validate unit provider_codes exist to avoid FK violations
        unit_repo = UnitRepository(self.data_session)
        existing_units = await unit_repo.get_by_codes(list(unit_codes))
        existing_codes = {unit.provider_code for unit in existing_units}
        missing_codes = sorted(unit_codes - existing_codes)
        if missing_codes:
            # Attempt to fetch and upsert missing units from provider
            logger.info(
                f"Found {len(missing_codes)} missing units in database, "
                f"attempting to fetch from provider"
            )
            try:
                await self._fetch_and_upsert_missing_units(missing_codes)
            except Exception as e:
                logger.error(f"Failed to fetch missing units from provider: {str(e)}")
                raise

            # Commit the upserted units so they're visible to subsequent queries
            await self.data_session.commit()
            logger.info("Committed upserted units to database")

            # Create a NEW repository instance after commit to get fresh data
            unit_repo = UnitRepository(self.data_session)
            logger.info(
                f"Reloading units after upsert - checking for "
                f"{len(unit_codes)} provider_codes"
            )

            existing_units = await unit_repo.get_by_codes(list(unit_codes))
            existing_codes = {unit.provider_code for unit in existing_units}
            missing_codes = sorted(unit_codes - existing_codes)

            logger.info(
                f"After upsert: found {len(existing_codes)} units, "
                f"still missing {len(missing_codes)} units"
            )

            # If still missing after fetch attempt, fail
            if missing_codes:
                raise ValueError(
                    "Unknown unit_id values in CSV (could not fetch from provider): "
                    f"{', '.join(missing_codes)}"
                )

        # Build mapping of provider_code to unit.id for DB operations
        unit_code_to_id = {unit.provider_code: unit.id for unit in existing_units}

        # Resolve carbon_report_module_id for each provider_code
        carbon_report_service = CarbonReportService(self.data_session)
        code_to_module_map: Dict[str, int] = {}
        reports_created = 0
        reports_reused = 0

        for provider_code in unit_codes:
            # Get the database ID for this provider_code
            unit_id = unit_code_to_id.get(provider_code)
            if not unit_id:
                raise ValueError(
                    f"Unit with provider_code={provider_code} not found "
                    f"after validation"
                )

            # Check if carbon report exists
            carbon_report = await carbon_report_service.get_by_unit_and_year(
                unit_id, self.year
            )

            if not carbon_report:
                # Create new carbon report (auto-creates all 7 modules)
                logger.info(
                    f"Creating carbon_report for provider_code={provider_code} "
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

            # Map provider_code (from CSV) to carbon_report_module_id
            code_to_module_map[provider_code] = carbon_report_module.id

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
        """Orchestrate CSV processing: setup → process rows → finalize"""
        try:
            # Setup: validate, load factors, move file
            setup_result = await self._setup_and_validate()

            # Resolve carbon_report_module_ids if needed (MODULE_PER_YEAR only)
            unit_to_module_map: Dict[str, int] | None = None
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
                await self.data_session.flush()  # Flush report/module creation

            # Initialize statistics and services
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
            data_entry_service = DataEntryService(self.data_session)
            emission_service = DataEntryEmissionService(self.data_session)

            # Process CSV rows
            batch: List[DataEntry] = []
            csv_reader = csv.DictReader(io.StringIO(setup_result["csv_text"]))

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

                assert (
                    data_entry is not None
                )  # Type guard: if no error, data_entry is valid

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
                            status_code=IngestionStatus.IN_PROGRESS,
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
                status_code=IngestionStatus.FAILED,
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
            status_code=IngestionStatus.IN_PROGRESS,
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
        csv_text = file_content.decode("utf-8")

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
                status_code=IngestionStatus.FAILED,
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
            unit_to_module_map: Optional mapping of provider_code
                               to carbon_report_module_id
                               for MODULE_PER_YEAR imports
        """
        try:
            handlers = setup_result["handlers"]
            factors_map = setup_result["factors_map"]
            expected_columns = setup_result["expected_columns"]

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

            # Lookup factor
            factor = None
            if kind_value:
                factor = lookup_factor(
                    kind=kind_value,
                    subkind=subkind_value,
                    factors_map=factors_map,
                )

            # Resolve handler and validate (entity-specific)
            (
                data_entry_type,
                handler,
                error_msg,
            ) = await self._resolve_handler_and_validate(
                filtered_row, factor, stats, row_idx, max_row_errors, setup_result
            )

            if error_msg:
                return None, error_msg, None

            if not data_entry_type or not handler:
                error_msg = "Failed to resolve handler and data_entry_type"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None

            # Resolve carbon_report_module_id
            carbon_report_module_id = None

            if unit_to_module_map is not None:
                # MODULE_PER_YEAR: resolve from unit_id
                # (which is actually provider_code)
                provider_code = row.get("unit_id")
                if provider_code is None or str(provider_code).strip() == "":
                    error_msg = "Missing unit_id in row"
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, error_msg, None

                provider_code = str(provider_code).strip()
                carbon_report_module_id = unit_to_module_map.get(provider_code)
                if not carbon_report_module_id:
                    error_msg = (
                        f"No carbon_report_module_id mapped for "
                        f"provider_code={provider_code}"
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

            # Validate payload with handler
            payload: Dict[str, str | int] = dict(filtered_row)
            payload["data_entry_type_id"] = data_entry_type.value
            payload["carbon_report_module_id"] = carbon_report_module_id
            payload["status"] = DataEntryStatusEnum.VALIDATED.value

            try:
                validated = handler.validate_create(payload)
            except Exception as validation_error:
                error_msg = f"Validation error: {validation_error}"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None

            # Build DataEntry
            primary_factor_id = factor.id if factor else None
            data = dict(validated.data)
            data["primary_factor_id"] = primary_factor_id

            data_entry = DataEntry(
                data_entry_type_id=data_entry_type,
                carbon_report_module_id=carbon_report_module_id,
                data=data,
            )

            return data_entry, None, factor

        except Exception as row_error:
            logger.error(f"Row {row_idx}: Error processing row: {str(row_error)}")
            error_msg = f"Row processing error: {row_error}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None

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

        # Update job status to COMPLETED with summary
        status_message = (
            f"Processed {stats['rows_processed']} rows: "
            f"{stats['rows_with_factors']} with factors, "
            f"{stats['rows_without_factors']} without factors, "
            f"{stats['rows_skipped']} skipped"
        )
        await self._update_job(
            status_message=status_message,
            status_code=IngestionStatus.COMPLETED,
            extra_metadata=dict(stats),
        )

        return {
            "status": "success",
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

        if user is None:
            logger.warning("No user context available for batch processing")
            raise ValueError("User context is required for batch processing")
        # 1. Bulk create data entries
        data_entries_response = await data_entry_service.bulk_create(
            batch, UserRead.model_validate(user)
        )

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
