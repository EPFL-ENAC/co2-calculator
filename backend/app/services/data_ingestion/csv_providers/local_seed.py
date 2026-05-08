"""Local CSV providers for seed scripts.

``LocalFactorCSVProvider`` runs factor CSV ingestion from local disk.
``LocalDataEntryCSVProvider`` runs data-entry CSV ingestion from local disk,
reusing the full ``ModulePerYearCSVProvider`` pipeline (row validation, batch
processing, emission computation, stats recomputation) without requiring a
running file-store service or DataIngestionJob records.
"""

import csv as csv_module
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.location import Location, TransportModeEnum
from app.services.data_ingestion.base_csv_provider import StatsDict
from app.services.data_ingestion.base_factor_csv_provider import FactorStatsDict
from app.services.data_ingestion.csv_providers.factors import (
    ModulePerYearFactorCSVProvider,
)
from app.services.data_ingestion.csv_providers.module_per_year import (
    ModulePerYearCSVProvider,
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

    async def _update_job(
        self,
        status_message: str,
        extra_metadata: dict | None = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
    ) -> None:
        # Local seed runs do not persist ingestion jobs.
        logger.debug(
            "LocalFactorCSVProvider state=%s, message=%s", state, status_message
        )
        return None

    # ------------------------------------------------------------------
    # Override: stay on the legacy bulk_create path during the batch loop
    # ------------------------------------------------------------------

    async def _upsert_batch(
        self,
        batch: List[Any],
        factor_repo: Any,
    ) -> int:
        """Local seed scripts have no DataIngestionJob and therefore no
        ``job_id`` to stamp on ``last_seen_job_id``.  The base class's
        ``_upsert_batch`` requires a job_id and raises if absent — so once
        a seed CSV exceeds BATCH_SIZE the main loop would crash.

        Override here to keep large seed runs on the legacy
        ``bulk_create`` path.  Seed scripts already assume an empty
        factor table (delete-and-insert semantics), so identity-key
        upsert is unnecessary; staying on bulk_create avoids the
        job_id requirement entirely.
        """
        # Late import to avoid circular import at module load.
        from app.services.factor_service import FactorService

        factor_service = FactorService(self.data_session)
        await self._process_batch(batch, factor_service)
        return len(batch)

    async def _finalize_and_commit(
        self,
        batch: List[Any],
        factor_service: Any,
        stats: FactorStatsDict,
        setup_result: Dict[str, Any],
        factor_repo: Any,  # signature-compat with base; legacy seed path
        # uses bulk_create and assumes the factor table starts empty
        # (seed scripts run against a fresh DB).
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


class LocalDataEntryCSVProvider(ModulePerYearCSVProvider):
    """Data-entry CSV provider that reads from local disk instead of the file store.

    Intended for seed scripts only.  No ``DataIngestionJob`` records are
    created and no file-store operations (upload / move) are performed.
    The full ``ModulePerYearCSVProvider`` pipeline is reused: row validation,
    factor lookup, batch inserts, emission computation and stats recomputation.

    Seed runs are NOT subject to ``BULK_PATH_PURE_ASYNC``: the runner-driven
    ``emission_recalc`` / ``aggregation`` chain is fired post-success by the
    request-scoped CSV ingest handlers, which seed scripts bypass entirely
    (their ``_update_job`` is a no-op and no DataIngestionJob exists).
    Honouring the gate would leave the seeded module with empty
    ``data_entry_emissions`` and zero stats, breaking dev DB bootstrap.
    The class therefore sets ``self.is_seed_run = True`` so the gate sites
    in ``base_csv_provider`` (``_process_batch`` emissions write,
    ``_recompute_module_stats``) always run inline for seed runs.

    Config keys
    -----------
    local_file_path : str
        Absolute path to the CSV file on disk.
    module_type_id : int
        Module type for the data entries being seeded.
    data_entry_type_id : int | None
        Fixed data-entry type for single-type CSVs.  Pass ``None`` when the
        type is determined per-row via factor lookup.
    year : int
        Reference year for the seeded data entries.
    location_fields : dict[str, str] | None
        Mapping from CSV source columns (e.g. ``"from"``) to data-dict keys
        (e.g. ``"origin_location_id"``).  Required for travel CSVs.
    transport_mode_value : str | None
        Transport mode used for location lookup (``"plane"`` or ``"train"``).
    """

    def __init__(self, config: Dict[str, Any], data_session: Any):
        super().__init__(
            config=config,
            user=None,
            job_session=None,
            data_session=data_session,
        )
        # Fake job object — never persisted, satisfies base-class attribute access.
        self.job = SimpleNamespace(  # type: ignore[assignment]
            module_type_id=config.get("module_type_id"),
            data_entry_type_id=config.get("data_entry_type_id"),
        )
        # Seed runs bypass ``BULK_PATH_PURE_ASYNC``: the runner chain that
        # would normally own emissions/stats writes is never fired here.
        self.is_seed_run = True
        self._local_file_path: str | None = config.get("local_file_path")
        self._location_fields: dict[str, str] | None = config.get("location_fields")
        transport_mode_value: str | None = config.get("transport_mode_value")
        self._transport_mode: TransportModeEnum | None = (
            TransportModeEnum(transport_mode_value) if transport_mode_value else None
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
    # Override: read from disk, skip file-store moves and DB job updates
    # ------------------------------------------------------------------

    async def _setup_and_validate(self) -> Dict[str, Any]:
        if not self._local_file_path:
            raise ValueError("Missing local_file_path in config")

        local_path = Path(self._local_file_path)
        if not local_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {self._local_file_path}")

        csv_text = local_path.read_text(encoding="utf-8-sig")

        # Pre-build location cache for travel CSVs before factor setup
        if self._location_fields and self._transport_mode is None:
            raise ValueError(
                "location_fields requires a valid transport_mode_value in config"
            )
        location_id_cache: dict[str, int] = {}
        if self._location_fields:
            location_id_cache = await self._build_location_cache(csv_text)

        # Setup handlers and factors (inherited from ModulePerYearCSVProvider)
        entity_setup = await self._setup_handlers_and_factors()

        await self._validate_csv_headers(
            csv_text,
            entity_setup["expected_columns"],
            entity_setup["required_columns"],
        )

        return {
            "csv_text": csv_text,
            "entity_type": self.entity_type,
            "handlers": entity_setup["handlers"],
            "factors_map": entity_setup["factors_map"],
            "factor_id_to_factor": entity_setup["factor_id_to_factor"],
            "expected_columns": entity_setup["expected_columns"],
            "required_columns": entity_setup["required_columns"],
            # Dummy value — _finalize_and_commit skips file-store operations
            "processing_path": None,
            "filename": local_path.name,
            "location_id_cache": location_id_cache,
        }

    # ------------------------------------------------------------------
    # Location cache for travel CSVs
    # ------------------------------------------------------------------

    async def _build_location_cache(self, csv_text: str) -> dict[str, int]:
        """Return a ``code -> location_id`` mapping for all codes in the CSV."""
        if not self._location_fields or not self._transport_mode:
            return {}

        source_columns = list(self._location_fields.keys())
        codes: set[str] = set()
        reader = csv_module.DictReader(io.StringIO(csv_text, newline=""))
        for row in reader:
            for source_col in source_columns:
                val = (row.get(source_col) or "").strip()
                if val:
                    codes.add(val)

        if not codes:
            return {}

        cache: dict[str, int] = {}

        if self._transport_mode == TransportModeEnum.plane:
            upper_codes = [c.upper() for c in codes]
            stmt = select(Location.id, Location.iata_code).where(
                col(Location.iata_code).in_(upper_codes),
                col(Location.transport_mode) == self._transport_mode,
            )
            results = await self.data_session.exec(stmt)
            for loc_id, iata_code in results:
                if iata_code and loc_id is not None:
                    cache[iata_code.upper()] = loc_id
        else:
            # Train: load all train locations and match by lowercase name
            stmt = select(Location.id, Location.name).where(
                col(Location.transport_mode) == self._transport_mode,
            )
            results = await self.data_session.exec(stmt)
            name_to_id: dict[str, int] = {}
            for loc_id, name in results:
                if name and loc_id is not None:
                    name_to_id[name.lower()] = loc_id
            for code in codes:
                loc_id = name_to_id.get(code.lower())
                if loc_id is not None:
                    cache[code] = loc_id

        # Warn for unresolved codes
        for code in sorted(codes):
            resolved = (
                code.upper() in cache
                if self._transport_mode == TransportModeEnum.plane
                else code in cache
            )
            if not resolved:
                logger.warning(
                    "Location not found: '%s' (mode=%s)",
                    code,
                    self._transport_mode.value,
                )

        return cache

    # ------------------------------------------------------------------
    # Override: inject location IDs before standard row processing
    # ------------------------------------------------------------------

    async def _process_row(
        self,
        row: Dict[str, str],
        row_idx: int,
        setup_result: Dict[str, Any],
        stats: StatsDict,
        max_row_errors: int,
        unit_to_module_map: Dict[str, int] | None = None,
    ) -> tuple[Any, str | None, Any, float | None]:
        if self._location_fields:
            row = dict(row)  # shallow copy to avoid mutating original
            location_id_cache = setup_result.get("location_id_cache", {})
            for source_col, data_key in self._location_fields.items():
                code = (row.get(source_col) or "").strip()
                if code:
                    lookup_key = (
                        code.upper()
                        if self._transport_mode == TransportModeEnum.plane
                        else code
                    )
                    loc_id = location_id_cache.get(lookup_key)
                    if loc_id is not None:
                        row[data_key] = str(loc_id)
        return await super()._process_row(
            row, row_idx, setup_result, stats, max_row_errors, unit_to_module_map
        )

    # ------------------------------------------------------------------
    # Override: skip file-store moves and job DB updates after processing
    # ------------------------------------------------------------------

    async def _update_job(
        self,
        status_message: str,
        extra_metadata: dict | None = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
    ) -> None:
        # Local seed runs do not persist ingestion jobs.
        logger.debug(
            "LocalDataEntryCSVProvider state=%s, message=%s", state, status_message
        )
        return None

    async def _finalize_and_commit(
        self,
        batch: List[Any],
        data_entry_service: Any,
        emission_service: Any,
        stats: StatsDict,
        setup_result: Dict[str, Any],
        batch_kg_co2eq_overrides: List[float | None],
    ) -> Dict[str, Any]:
        if batch:
            await self._process_batch(
                batch,
                data_entry_service,
                emission_service,
                self.user,
                batch_kg_co2eq_overrides,
            )
            stats["batches_processed"] += 1

        await self.data_session.flush()
        await self._recompute_module_stats()

        result = self._compute_ingestion_result(stats)

        logger.info(
            f"Local seed completed: {stats['rows_processed']} rows processed, "
            f"{stats['rows_skipped']} skipped, "
            f"{stats['row_errors_count']} errors"
        )
        return {
            "state": IngestionState.FINISHED,
            "result": result,
            "inserted": stats["rows_processed"],
            "skipped": stats["rows_skipped"],
            "stats": stats,
        }
