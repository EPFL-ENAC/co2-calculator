import asyncio
import csv
import io
import time
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict

from sqlmodel import col, select

from app.api.v1.files import make_files_store
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
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
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.data_entry import (
    DATA_ENTRY_META_FIELDS,
    BaseModuleHandler,
    ModuleHandler,
)
from app.seed.seed_helper import load_factors_map
from app.services.carbon_report_service import CarbonReportService
from app.services.data_entry_emission_service import (
    KG_CO2EQ_OVERRIDE_KEY,
    DataEntryEmissionService,
)
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.module_handler_service import ModuleHandlerService
from app.services.unit_service import UnitService
from app.services.user_service import UserService

logger = get_logger(__name__)

# Minimum wall-clock seconds between two progress writes for the same job.
# Progress is checked per-row (cheap monotonic read) but the DB write + log
# line only fire this often, so a long CPU phase shows motion without
# hammering the session.
PROGRESS_REPORT_INTERVAL_S = 2.0


def _is_blank_data_row(row: Dict[str, str], required_columns: set[str]) -> bool:
    """Return True when every required column is empty or absent in the raw row."""
    if not required_columns:
        return False
    return all(not (row.get(col) or "").strip() for col in required_columns)


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


def _guard_factors_required(
    *,
    factors_map: Dict[str, Any],
    handlers: list[Any],
    module_label: str,
    year: int | None,
) -> None:
    """Fail-fast when an ingest needs factors but the map is empty.

    For modules whose handler declares ``require_factor_to_match=True``
    (e.g. equipment), every row's emission record needs a matched
    ``Factor`` to populate ``primary_factor_id``.  When the factors
    table has nothing for this (module, year) tuple the row-level loop
    would record one "no matching factor" error per row — a 50 000-row
    CSV produces 50 000 identical messages and the operator has to
    scroll past them to find out the real issue is that they forgot to
    upload factors first.

    Raised at setup time instead, so ``_setup_and_validate``'s
    try/except wraps it into one ``FINISHED + ERROR`` with a
    single-line ``status_message``.  Caller passes a human-readable
    ``module_label`` (e.g. ``"Equipment"``) so the message tells the
    operator *which* upload is missing without them having to know
    enum ints.
    """
    if factors_map:
        return
    if not any(getattr(h, "require_factor_to_match", False) for h in handlers):
        return
    year_str = f"year={year}" if year is not None else "the configured year"
    raise ValueError(
        f"No factors available for module={module_label} {year_str}. "
        "Upload factors for this module/year before ingesting data — "
        "every row needs a matched Factor for primary_factor_id."
    )


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
        # Track which missing units we've already warned about (deduplication)
        self._missing_units_logged: set[str] = set()
        # module_id → unit_id, filled by _resolve_carbon_report_modules;
        # used to stamp the denormalized DataEntry.unit_id at row build.
        self._module_to_unit_id: Dict[int, int] = {}
        # Cache for carbon_report_module_id -> year mapping (avoid per-row DB queries)
        self._year_cache: Dict[int, int] = {}
        # Progress reporting: current phase label + throttle/rate bookkeeping.
        self._phase = ""
        self._phase_started_at = 0.0
        self._last_report_at = 0.0
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

    async def _load_handlers_and_factors(
        self, entry_types: List[DataEntryTypeEnum]
    ) -> tuple[List[Any], Dict[str, Any]]:
        """
        Load deduplicated handlers and the merged factors map for the
        given data entry types.

        Year is required: factor lookups during row processing key on
        ``{type}:{year}:{kind}:{subkind}``, so a missing year would
        silently miss every factor and import rows with
        primary_factor_id=None.
        """
        if not self.year:
            raise ValueError(
                f"year is required for {self.entity_type.name} entity type"
            )

        # Deduplicate handlers by class to avoid multiple identical
        # instances (e.g., EquipmentModuleHandler registered for
        # it/scientific/other)
        handlers: List[Any] = []
        seen_handler_classes: set[type[Any]] = set()
        for entry_type in entry_types:
            handler = BaseModuleHandler.get_by_type(entry_type)
            handler_class: type[Any] = type(handler)
            if handler_class not in seen_handler_classes:
                handlers.append(handler)
                seen_handler_classes.add(handler_class)

        factors_map: Dict[str, Any] = {}
        for entry_type in entry_types:
            type_factors = await load_factors_map(
                self.data_session, entry_type, self.year
            )
            factors_map.update(type_factors)
            # Yield between factor-type merges: building a large factors_map
            # (tens of thousands of factors) is a CPU burst that would
            # otherwise block the event loop during setup.
            await asyncio.sleep(0)

        return handlers, factors_map

    def _assemble_setup_result(
        self,
        *,
        handlers: List[Any],
        factors_map: Dict[str, Any],
        module_label: str,
        required_columns: set[str],
    ) -> Dict[str, Any]:
        """
        Build the setup dict returned by ``_setup_handlers_and_factors``.

        Runs the require-factor guard, derives expected columns, and
        builds the factor_id -> factor map for O(1) lookup during row
        processing (avoids an O(n) scan of factors_map per row).
        """
        _guard_factors_required(
            factors_map=factors_map,
            handlers=handlers,
            module_label=module_label,
            year=self.year,
        )

        expected_columns = _get_expected_columns_from_handlers(handlers)

        factor_id_to_factor: Dict[int, Any] = {}
        for factor in factors_map.values():
            factor_id = getattr(factor, "id", None)
            if factor_id is not None:
                factor_id_to_factor[factor_id] = factor

        logger.info(
            f"Setup complete for {self.entity_type.name}: "
            f"handlers={len(handlers)}, "
            f"factors={len(factors_map)}, "
            f"factor_id_to_factor={len(factor_id_to_factor)}, "
            f"expected_columns={len(expected_columns)}, "
            f"required_columns={len(required_columns)}"
        )

        return {
            "handlers": handlers,
            "factors_map": factors_map,
            "factor_id_to_factor": factor_id_to_factor,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
        }

    def _resolve_type_from_config_or_category(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
        row_idx: int,
        stats: StatsDict,
        max_row_errors: int,
    ) -> tuple[DataEntryTypeEnum | None, "ModuleHandler | None"]:
        """
        Shared Priority 1/2 of data_entry_type resolution.

        Priority 1: configured ``data_entry_type_id`` from job config
        (cast through int so string ids from JSON config work).
        Priority 2: the single handler's category column (e.g.
        ``equipment_category``) mapping directly to a DataEntryTypeEnum
        name.

        Returns (data_entry_type, handler); either may be None — callers
        decide whether that is an error (MODULE_UNIT_SPECIFIC) or the
        cue for factor-based inference (MODULE_PER_YEAR).
        """
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is not None:
            data_entry_type = DataEntryTypeEnum(int(configured_data_entry_type_id))
            return data_entry_type, handlers[0] if handlers else None

        handler = handlers[0] if len(handlers) == 1 else None
        if handler is None:
            return None, None

        resolved_type: DataEntryTypeEnum | None = (
            self._resolve_data_entry_type_from_category(
                filtered_row, handler, row_idx, stats, max_row_errors
            )
        )
        return resolved_type, handler

    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """
        Extract kind and subkind values from filtered row.

        Tries each handler's kind_field/subkind_field first, then falls
        back to common field names. Works for single- and multi-handler
        providers alike.

        Returns: (kind_value, subkind_value)
        """
        # Try to find kind/subkind using each handler's fields
        for handler in handlers:
            if handler.kind_field and handler.kind_field in filtered_row:
                kind_value = filtered_row.get(handler.kind_field, "")
                subkind_value = (
                    filtered_row.get(handler.subkind_field)
                    if handler.subkind_field
                    else None
                )
                return kind_value, subkind_value

        # Fallback: try common field names
        for handler in handlers:
            subkind_value = None
            if handler.subkind_field and handler.subkind_field in filtered_row:
                subkind_value = filtered_row.get(handler.subkind_field)

            for kind_field_name in ("kind", "Kind", "KIND"):
                if kind_field_name in filtered_row:
                    kind_value = filtered_row.get(kind_field_name, "")
                    return kind_value, subkind_value

        # Last resort: return empty if nothing found
        return "", None

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

        # Bulk-resolve the existing map in ONE join over
        # units ⨝ carbon_reports(year) ⨝ carbon_report_modules(module_type)
        # instead of 2 queries per unit.  ~2.5k units → one round-trip;
        # the per-unit path below only runs for units that still need a
        # carbon_report created for this year.
        map_stmt = (
            select(Unit.institutional_id, CarbonReportModule.id, Unit.id)
            .join(CarbonReport, col(CarbonReport.unit_id) == col(Unit.id))
            .join(
                CarbonReportModule,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(
                col(CarbonReport.year) == self.year,
                col(CarbonReportModule.module_type_id) == module_type_id,
            )
        )
        full_map: Dict[str, int] = {}
        for institutional_id, module_id, unit_db_id in (
            await self.data_session.execute(map_stmt)
        ).all():
            if institutional_id is None:
                continue
            full_map[institutional_id] = module_id
            self._module_to_unit_id[module_id] = unit_db_id
        logger.info(
            f"Bulk-resolved {len(full_map)} existing "
            f"carbon_report_modules for year={self.year}, "
            f"module_type_id={module_type_id}"
        )

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

        logger.info(f"Found {len(unit_codes)} unique unit institutional_ids in CSV")
        logger.debug("Unique unit institutional_ids: %s", sorted(unit_codes))

        # Scope the map to the CSV's units.  The bulk join above covers
        # EVERY unit with a report for this (year, module_type) — using
        # it unfiltered would widen downstream consumers, most
        # dangerously ``_delete_existing_entries_for_module_per_year``,
        # which would then wipe CSV-uploaded entries of units this file
        # doesn't even mention (and drag the DELETE across the whole
        # year's modules).
        code_to_module_map: Dict[str, int] = {
            code: full_map[code] for code in unit_codes if code in full_map
        }

        # Only units NOT already in the bulk map need per-unit work:
        # either their carbon_report for this year doesn't exist yet
        # (create it — auto-creates all modules), or the unit itself is
        # unknown (surfaced loudly below; its rows will be skipped).
        unresolved_codes = sorted(unit_codes - set(code_to_module_map))
        reports_created = 0
        if unresolved_codes:
            unit_repo = UnitRepository(self.data_session)
            existing_units = await unit_repo.get_by_institutional_ids(unresolved_codes)
            unit_code_to_id = {
                unit.institutional_id: unit.id for unit in existing_units
            }
            unknown_codes = sorted(set(unresolved_codes) - set(unit_code_to_id))
            if unknown_codes:
                # Not silently absorbed into per-row warnings: one loud
                # summary so a CSV referencing units missing from the
                # units table is diagnosable from a single log line.
                logger.error(
                    f"{len(unknown_codes)} unit_institutional_ids from the "
                    f"CSV are not in the units table — every row for them "
                    f"will be skipped: {unknown_codes[:50]}"
                )

            carbon_report_service = CarbonReportService(self.data_session)
            for unit_institutional_id in unresolved_codes:
                if unit_institutional_id in self._missing_unit_codes:
                    continue
                unit_id = unit_code_to_id.get(unit_institutional_id)
                if not unit_id:
                    continue  # already reported in unknown_codes above

                # Not in the joined map, so the report may be missing —
                # but check first: the report can exist with the module
                # row absent, and create() would raise on a duplicate.
                carbon_report = await carbon_report_service.get_by_unit_and_year(
                    unit_id, self.year
                )
                if not carbon_report:
                    logger.info(
                        "Creating carbon_report for "
                        f"institutional_id={unit_institutional_id} "
                        f"(unit_id={unit_id}), year={self.year}"
                    )
                    carbon_report = await carbon_report_service.create(
                        CarbonReportCreate(unit_id=unit_id, year=self.year)
                    )
                    reports_created += 1

                carbon_report_module = (
                    await carbon_report_service.module_service.get_module(
                        carbon_report.id, module_type_id
                    )
                )
                if not carbon_report_module:
                    raise ValueError(
                        f"No carbon_report_module found for "
                        f"carbon_report_id={carbon_report.id}, "
                        f"module_type_id={module_type_id}"
                    )
                code_to_module_map[unit_institutional_id] = carbon_report_module.id
                self._module_to_unit_id[carbon_report_module.id] = unit_id

        logger.info(
            f"Resolved carbon_report_module_ids: "
            f"{len(code_to_module_map)} mapped "
            f"({reports_created} new reports created)"
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

        Note: MODULE_UNIT_SPECIFIC uses append-only strategy (no deletion).

        Args:
            unit_to_module_map: Mapping of unit ID to module ID
            stats: Statistics dict to update
            data_entry_service: DataEntryService instance to use
        """

        if not (self.job and self.job.module_type_id):
            logger.info("No job module_type_id — skipping pre-import deletion")
            return

        module_type = ModuleTypeEnum(self.job.module_type_id)
        # If the job targets a specific data_entry_type_id, only delete
        # entries for that type. Deleting all types for the module would
        # wipe sibling submodules (e.g. uploading research_facilities
        # data would erase mice_and_fish_animal_facilities entries).
        if self.job.data_entry_type_id is not None:
            valid_entry_types = [DataEntryTypeEnum(self.job.data_entry_type_id)]
        else:
            valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

        if self.year is None:
            raise ValueError("year is required for MODULE_PER_YEAR deletion")

        # Full-year replace: per-year CSVs are complete exports, so ONE
        # indexed DELETE on the denormalized ``data_entries.year`` column
        # replaces every prior row of (year, types, source) — no module
        # resolution, no audit trail (the bulk path skips audit on insert
        # too; the job row is the operator-facing record).
        deleted_rows = await data_entry_service.repo.bulk_delete_by_source_year(
            year=self.year,
            data_entry_type_ids=[t.value for t in valid_entry_types],
            source=DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value,
        )

        logger.info(
            f"Deleted {deleted_rows} data entries from previous CSV uploads "
            f"(year={self.year}, {len(valid_entry_types)} types, full replace)"
        )

    def _enter_phase(self, phase: str) -> None:
        """Mark the start of a pipeline phase (resets the rate/ETA baseline)."""
        self._phase = phase
        self._phase_started_at = time.monotonic()

    @staticmethod
    def _format_progress(
        phase: str, processed: int | None, total: int | None, elapsed: float
    ) -> str:
        """Human-readable progress line with throughput + rough ETA."""
        if not processed or not total:
            return phase
        rate = processed / max(elapsed, 1e-3)
        eta = (total - processed) / rate if rate > 0 else 0.0
        return f"{phase}: {processed}/{total} rows ({rate:.0f}/s, ~{eta:.0f}s left)"

    async def _report(
        self,
        phase: str,
        *,
        processed: int | None = None,
        total: int | None = None,
        stats: "StatsDict | None" = None,
        force: bool = False,
    ) -> None:
        """Throttled progress write to the job row + an INFO log line.

        Safe to call per-row: only the monotonic clock is read unless a
        write is due (every ``PROGRESS_REPORT_INTERVAL_S``) or ``force``.
        """
        now = time.monotonic()
        if not force and now - self._last_report_at < PROGRESS_REPORT_INTERVAL_S:
            return
        self._last_report_at = now

        msg = self._format_progress(
            phase, processed, total, now - self._phase_started_at
        )
        meta: Dict[str, Any] = dict(stats) if stats else {}
        meta["progress"] = {"phase": phase, "processed": processed, "total": total}
        logger.info(msg)
        await self._update_job(
            status_message=msg,
            state=IngestionState.RUNNING,
            result=None,
            extra_metadata=meta,
        )

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
                self._enter_phase("Resolving modules")
                await self._report("Resolving modules", force=True)
                unit_to_module_map = await self._resolve_carbon_report_modules(
                    setup_result["csv_text"]
                )
                # Store for later use in _recompute_module_stats
                self._unit_to_module_map = unit_to_module_map
                await self.data_session.flush()  # Flush report/module creation

                # Delete existing entries from previous CSV_MODULE_PER_YEAR uploads
                self._enter_phase("Deleting previous entries")
                await self._report("Deleting previous entries", force=True)
                await self._delete_existing_entries_for_module_per_year(
                    unit_to_module_map, stats, data_entry_service
                )

            # Process CSV rows
            copy_batch_size = get_settings().INGEST_COPY_BATCH_SIZE
            # Rough row count for progress/ETA (header line excluded); the CSV
            # text is already in memory, so counting newlines is cheap.
            total_rows = max(setup_result["csv_text"].count("\n") - 1, 0)
            self._enter_phase("Parsing rows")
            await self._report(
                "Parsing rows", processed=0, total=total_rows, stats=stats, force=True
            )
            batch: List[DataEntry] = []
            # Parallel list of kg_co2eq overrides aligned with `batch` by index.
            # Carried out-of-band so kg_co2eq never lands in DataEntry.data.
            batch_kg_co2eq_overrides: List[float | None] = []
            # Track seen user_institutional_ids per module to catch intra-CSV duplicates
            seen_institutional_ids: Dict[int, set] = {}
            csv_reader = csv.DictReader(
                io.StringIO(setup_result["csv_text"], newline="")
            )

            for row_idx, row in enumerate(csv_reader, start=1):
                # Row processing is mostly CPU (parse/validate, cached
                # lookups) — with 50k-row COPY batches nothing else
                # would run on the event loop for the whole file.
                # Yield every 100 rows so /healthz & /ready stay under the
                # liveness/readiness probe timeout even on a CPU-tight pod;
                # a 1000-row stretch could exceed 2s and trigger a restart.
                if row_idx % 100 == 0:
                    await asyncio.sleep(0)
                    # Throttled internally to PROGRESS_REPORT_INTERVAL_S, so the
                    # long parse/validate phase shows live throughput + ETA
                    # instead of going silent for tens of seconds.
                    await self._report(
                        "Parsing rows",
                        processed=row_idx,
                        total=total_rows,
                        stats=stats,
                    )
                # if empty row, skip
                if not row:
                    continue
                # Skip completely blank rows
                if not any(
                    value is not None and str(value).strip() for value in row.values()
                ):
                    continue

                # Process single row, returns
                # (data_entry, error_msg, factor, kg_co2eq_override)
                (
                    data_entry,
                    error_msg,
                    factor,
                    kg_co2eq_override,
                ) = await self._process_row(
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
                # TODO: refactor, should not be done in base_csv_provider but elsewhere
                # process or task or sql
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
                batch_kg_co2eq_overrides.append(kg_co2eq_override)
                if factor:
                    stats["rows_with_factors"] += 1
                else:
                    stats["rows_without_factors"] += 1
                stats["rows_processed"] += 1

                # Flush when the COPY batch is full
                if len(batch) >= copy_batch_size:
                    await self._process_batch(
                        batch,
                        data_entry_service,
                        emission_service,
                        self.user,
                        batch_kg_co2eq_overrides,
                    )
                    stats["batches_processed"] += 1
                    logger.info(
                        f"Processed batch {stats['batches_processed']}: "
                        f"{stats['rows_processed']} rows total"
                    )
                    batch = []
                    batch_kg_co2eq_overrides = []
                    # Update job progress every batche
                    if stats["batches_processed"]:
                        await self._update_job(
                            status_message=f"Processing: {stats['rows_processed']}",
                            state=IngestionState.RUNNING,
                            result=None,
                            extra_metadata=dict(stats),
                        )

            # Finalize: process remaining batch, move file, update job
            self._enter_phase("Inserting")
            await self._report(
                "Inserting", processed=stats["rows_processed"], force=True
            )
            return await self._finalize_and_commit(
                batch,
                data_entry_service,
                emission_service,
                stats,
                setup_result,
                batch_kg_co2eq_overrides,
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
        factor_id_to_factor = entity_setup["factor_id_to_factor"]
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
                status_message=f"Wrong CSV format or encoding: {error_message}",
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
            "factor_id_to_factor": factor_id_to_factor,
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
    ) -> tuple[DataEntry | None, str | None, Any | None, float | None]:
        """
        Process a single CSV row.
        Returns (DataEntry, error_msg, factor, kg_co2eq_override) tuple.
        If error_msg is not None, row processing failed and error was recorded.

        ``kg_co2eq_override`` is carried out-of-band so it never lands in
        ``DataEntry.data``; the caller passes it transiently to
        ``prepare_create`` when emissions are built.

        Args:
            unit_to_module_map: Optional mapping of institutional_id
                               to carbon_report_module_id
                               for MODULE_PER_YEAR imports
        """
        try:
            handlers = setup_result["handlers"]
            expected_columns = setup_result["expected_columns"]
            required_columns = setup_result.get("required_columns", set())

            # Template scaffolding rows keep required columns empty; skip them
            # before stripping blanks into filtered_row.
            if required_columns and _is_blank_data_row(row, required_columns):
                stats["rows_skipped"] += 1
                return None, None, None, None

            # Extract kg_co2eq override from the raw row (carried out-of-band).
            # Bypasses expected_columns intentionally: not every handler lists
            # kg_co2eq there, but it's still a valid override when present.
            kg_co2eq_override: float | None = None
            raw_kg = row.get("kg_co2eq")
            if raw_kg is not None and raw_kg.strip() != "":
                try:
                    kg_co2eq_override = float(raw_kg)
                except (ValueError, TypeError):
                    # Surface unparseable overrides at WARNING so operators see
                    # the silent fallback to formula-based emissions in the log.
                    logger.warning(
                        f"Row {row_idx}: invalid kg_co2eq value {raw_kg!r}, "
                        f"ignoring override"
                    )

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
                return None, error_msg, None, None

            if not data_entry_type or not handler:
                error_msg = "Failed to resolve handler and data_entry_type"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None, None

            # Resolve primary_factor_id from in-memory factors_map (NOT DB query!)
            # This avoids 100k+ DB queries - factors already loaded in setup phase
            primary_factor_id: int | None = None
            if "factors_map" in setup_result and handler.kind_field:
                kind_value, subkind_value = self._extract_kind_subkind_values(
                    filtered_row, handlers
                )
                # Defense in depth: the setup-time guard in
                # _load_handlers_and_factors raises before any row
                # reaches this method,
                # so reaching this branch with a falsy year would mean a
                # future caller bypassed setup. Use the same `not self.year`
                # check the setup-time guard uses so both layers reject the
                # same set of values (None and 0); a stricter `is None` check
                # would let `year=0` rebuild the `:0:` silent-miss key.
                if not self.year:
                    raise ValueError(
                        "year must be set (and non-zero) before processing "
                        "rows; setup-time guard was bypassed"
                    )
                year_value = self.year
                # Build lookup key same way as load_factors_map does
                key_full = (
                    f"{data_entry_type.value}:"
                    f"{year_value}:"
                    f"{(kind_value or '').lower()}:"
                    f"{(subkind_value or '').lower()}"
                )
                factor = setup_result["factors_map"].get(key_full)
                # Fallback: try without subkind
                if not factor and subkind_value:
                    key_kind = (
                        f"{data_entry_type.value}:"
                        f"{year_value}:"
                        f"{(kind_value or '').lower()}"
                    )
                    factor = setup_result["factors_map"].get(key_kind)
                if factor:
                    primary_factor_id = factor.id

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
                    return None, error_msg, None, None

                unit_institutional_id = str(unit_institutional_id).strip()

                # Skip rows with missing units
                if unit_institutional_id in self._missing_unit_codes:
                    # Only log warning once per unique institutional_id (deduplication)
                    if unit_institutional_id not in self._missing_units_logged:
                        logger.warning(
                            f"Unit '{unit_institutional_id}' not found in database - "
                            f"skipping all rows for this unit"
                        )
                        self._missing_units_logged.add(unit_institutional_id)
                    error_msg = f"Unit '{unit_institutional_id}' not found"
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, error_msg, None, None

                carbon_report_module_id = unit_to_module_map.get(unit_institutional_id)
                if not carbon_report_module_id:
                    error_msg = (
                        f"No carbon_report_module_id mapped for "
                        f"institutional_id={unit_institutional_id}"
                    )
                    self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                    return None, error_msg, None, None
            elif self.carbon_report_module_id:
                # MODULE_UNIT_SPECIFIC: use pre-configured value
                carbon_report_module_id = self.carbon_report_module_id
            else:
                # Neither mapping nor pre-configured value available
                error_msg = "Missing carbon_report_module_id"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg, None, None

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
                return None, error_msg, None, None

            # Build DataEntry
            data = dict(validated.data)

            # CSV-time enrichment hook. Default no-op; the train handler uses
            # it to resolve origin_name/destination_name → *_natural_key via
            # a Location lookup so the recalc-time pre_compute can compute
            # distance. Returning a non-None error_msg skips the row.
            data, enrich_error = await handler.enrich_csv_row(data, self.data_session)
            if enrich_error is not None:
                self._record_row_error(stats, row_idx, enrich_error, max_row_errors)
                return None, enrich_error, None, None

            handler_service = ModuleHandlerService(self.data_session)
            if primary_factor_id and "factor_id_to_factor" in setup_result:
                factor = setup_result["factor_id_to_factor"].get(primary_factor_id)
                if factor is not None:
                    data = await handler_service.populate_defaults(
                        handler, data, factor
                    )

            # Persist the override on the data
            # entry under the reserved ``KG_CO2EQ_OVERRIDE_KEY`` carrier so
            # the async recalc path (``upsert_by_data_entry`` →
            # ``prepare_create``) still honors it.  The parallel list is
            # kept for the legacy inline path's existing flow.
            if kg_co2eq_override is not None:
                data[KG_CO2EQ_OVERRIDE_KEY] = kg_co2eq_override

            data_entry = DataEntry(
                data_entry_type_id=data_entry_type,
                carbon_report_module_id=carbon_report_module_id,
                data=data,
                # Denormalized scope columns — back the per-year
                # full-replace delete without module resolution.
                year=self.year,
                unit_id=self._module_to_unit_id.get(carbon_report_module_id),
            )

            return data_entry, None, None, kg_co2eq_override

        except Exception as row_error:
            logger.error(f"Row {row_idx}: Error processing row: {str(row_error)}")
            error_msg = f"Row processing error: {row_error}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg, None, None

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
        batch_kg_co2eq_overrides: List[float | None],
    ) -> Dict[str, Any]:
        """
        Finalize: process remaining batch, move file to processed/, update job.
        """
        # Process final batch (remaining rows below the COPY batch size)
        if batch:
            await self._process_batch(
                batch,
                data_entry_service,
                emission_service,
                self.user,
                batch_kg_co2eq_overrides,
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
        metadata_update = {}
        if not move_result:
            logger.warning(
                f"Failed to move file from {processing_path} to {processed_path}"
            )
            metadata_update["processed_file_path"] = processing_path
        else:
            metadata_update = {"processed_file_path": processed_path}

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
        metadata_for_job.update(metadata_update)
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
        batch_kg_co2eq_overrides: List[float | None],
    ) -> None:
        """Process a batch of data entries: bulk insert entries and emissions.

        ``batch_kg_co2eq_overrides`` is index-aligned with ``batch``. Values are
        applied transiently when emissions are built — they never enter
        ``DataEntry.data``.
        """
        if not batch:
            return

        logger.info(f"Processing batch of {len(batch)} entries")

        # Pre-fetch years for all carbon_report_modules in this batch
        # This avoids per-row DB queries in emission_service.prepare_create
        module_ids: set[int] = {
            entry.carbon_report_module_id
            for entry in batch
            if entry.carbon_report_module_id is not None
            and entry.carbon_report_module_id not in self._year_cache
        }
        if module_ids:
            stmt = (
                select(CarbonReportModule, CarbonReport)
                .join(
                    CarbonReport,
                    CarbonReport.id == CarbonReportModule.carbon_report_id,  # type: ignore[arg-type]
                )
                .where(col(CarbonReportModule.id).in_(list(module_ids)))
            )
            results = await self.data_session.exec(stmt)
            for module, report in results:
                if module.id is not None and report.year is not None:
                    self._year_cache[module.id] = report.year
            logger.debug(f"Cached years for {len(module_ids)} carbon_report_modules")

        # Determine source based on entity_type
        source = self._get_source_from_entity_type()

        # 1. Bulk insert data entries via COPY (no ids needed here — the
        # chained emission_recalc re-reads entries from the DB).
        inserted = await data_entry_service.bulk_copy(
            batch,
            job_id=self.job_id,
            source=source.value if source else None,
            created_by_id=self.job_id,
        )
        logger.debug(f"COPY-inserted {inserted} data entries")
        await self.data_session.commit()
        return None

    async def _recompute_module_stats(self) -> None:
        """
        Plan 310-D —  the runner-driven
        ``aggregation`` handler (chained by ``emission_recalc`` after the
        data ingest's recalc finishes) owns ``carbon_reports.stats`` writes
        for the bulk path.
        """
        return

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
