import asyncio
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, TypedDict

from pydantic import ValidationError

from app.core.config import get_settings
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
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.models.user import User
from app.modules.emissions.taxonomy import EmissionTypeResolutionError
from app.modules_planner.purchase.derived_factors import (
    PURCHASE_SOURCE_TYPES,
    derive_planner_purchase_factors,
)
from app.repositories.factor_repo import FactorRepository
from app.schemas.factor import BaseFactorHandler
from app.seed.seed_helper import get_factor_emission_type_id
from app.services.data_ingestion.base_csv_provider import (
    _format_pydantic_validation_error,
    _validate_file_path,
)
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.factor_service import FactorService
from app.utils.csv_dialect import csv_dict_reader

logger = get_logger(__name__)


class FactorStatsDict(TypedDict):
    rows_processed: int
    rows_skipped: int
    batches_processed: int
    row_errors: list[dict[str, Any]]
    row_errors_count: int
    # stale rows superseded by this upload; see _delete_stale_factors
    factors_deleted: int
    factors_upserted: int


def _get_expected_columns_from_handlers(handlers: list[Any]) -> set[str]:
    expected_columns: set[str] = set()
    for handler in handlers:
        expected_columns.update(handler.expected_columns)
    return expected_columns


def _get_required_columns_from_handler(handler: Any) -> set[str]:
    return handler.required_columns


class BaseFactorCSVProvider(DataIngestionProvider, ABC):
    """Base class for CSV factor ingestion providers."""

    def __init__(
        self,
        config: dict[str, Any],
        user: User | None = None,
        job_session: Any = None,
        data_session: Any = None,
    ):
        super().__init__(config, user, job_session, data_session=data_session)
        self.job_id = config.get("job_id")
        self.module_type_id = config.get("module_type_id")
        self.data_entry_type_id = config.get("data_entry_type_id")
        self.year = config.get("year")
        raw_file_path = config.get("file_path")
        self.source_file_path = (
            urllib.parse.unquote(raw_file_path) if raw_file_path else None
        )
        if self.source_file_path:
            _validate_file_path(self.source_file_path)
        self._files_store: Any = None
        # dets actually written by this job's upserts — the stale sweep is
        # scoped to exactly these ("you replace what you upload"), so a
        # partial module CSV can never wipe sibling dets it didn't carry.
        self._upserted_det_ids: set[int] = set()
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

    async def fetch_data(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def transform_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return raw_data

    async def _load_data(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        return {"inserted": 0, "skipped": 0, "errors": 0}

    async def ingest(
        self,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

    async def process_csv_in_batches(self) -> dict[str, Any]:
        try:
            setup_result = await self._setup_and_validate()

            max_row_errors = int(self.config.get("max_row_errors", 100))
            stats: FactorStatsDict = {
                "rows_processed": 0,
                "rows_skipped": 0,
                "batches_processed": 0,
                "row_errors": [],
                "row_errors_count": 0,
                "factors_deleted": 0,
                "factors_upserted": 0,
            }
            factor_service = FactorService(self.data_session)
            factor_repo = FactorRepository(self.data_session)
            # Plan 310B: upsert in place (preserves factor.id so existing
            # DataEntryEmission.primary_factor_id FKs stay valid).  No bulk
            # delete: factors absent from the new CSV are kept and surfaced
            # as stale via last_seen_job_id.

            copy_batch_size = get_settings().INGEST_COPY_BATCH_SIZE
            batch: list[Factor] = []
            csv_reader = csv_dict_reader(setup_result["csv_text"])

            for row_idx, row in enumerate(csv_reader, start=1):
                # Row processing is pure CPU (validate, in-memory resolution)
                # and the COPY batch is 50k rows, so without an explicit yield
                # a large factor file (tens of thousands of rows) starves the
                # event loop for its whole duration — freezing the API and SSE.
                # Mirror the data-entry provider and yield regularly.
                if row_idx % 1000 == 0:
                    await asyncio.sleep(0)
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

                if factor is None:
                    raise ValueError("Factor is None without error message")
                batch.append(factor)
                stats["rows_processed"] += 1

                if len(batch) >= copy_batch_size:
                    upserted = await self._upsert_batch(batch, factor_repo)
                    stats["factors_upserted"] += upserted
                    stats["batches_processed"] += 1
                    logger.info(
                        f"Processed batch {stats['batches_processed']}: "
                        f"{stats['rows_processed']} rows total"
                    )
                    batch = []

                    if stats["batches_processed"] % 5 == 0 and self.job_id is not None:
                        await self._update_job(
                            status_message=f"Processing: {stats['rows_processed']}",
                            state=IngestionState.RUNNING,
                            result=None,
                            extra_metadata=dict(stats),
                        )

            result = await self._finalize_and_commit(
                batch, factor_service, stats, setup_result, factor_repo
            )
            await self._derive_dependent_factors(result)
            return result
        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}", exc_info=True)
            await self.data_session.rollback()
            if self.job_id is not None:
                await self._update_job(
                    status_message=f"Processing failed: {str(e)}",
                    state=IngestionState.FINISHED,
                    result=IngestionResult.ERROR,
                    extra_metadata={"error": str(e)},
                )
            raise

    async def _setup_and_validate(self) -> dict[str, Any]:
        if self.year is None:
            raise ValueError("year is required for factor CSV ingestion")
        if self.job_id is not None:
            await self._update_job(
                status_message="Starting CSV processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={},
            )
        await self.data_session.flush()

        tmp_path = self.source_file_path
        if not tmp_path:
            raise ValueError("Missing file_path in config")
        _validate_file_path(tmp_path)
        processing_path = await self._move_to_processing(tmp_path)
        filename = processing_path.split("/")[-1]

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
        }

    def _validate_csv_headers(
        self,
        csv_text: str,
        expected_columns: set[str],
        required_columns: set[str],
    ) -> None:
        strict_mode = self.config.get("strict_column_validation", False)
        rows_to_check = 5

        validation_reader = csv_dict_reader(csv_text)
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
        row: dict[str, str],
        row_idx: int,
        setup_result: dict[str, Any],
        stats: FactorStatsDict,
        max_row_errors: int,
        factor_service: FactorService,
    ) -> tuple[Factor | None, str | None]:
        try:
            # Resolve data_entry_type first
            data_entry_type = self._resolve_data_entry_type(
                row, setup_result, row_idx, stats, max_row_errors
            )
            if data_entry_type is None:
                return None, "Missing data_entry_type"

            handler = BaseFactorHandler.get_by_type(data_entry_type)

            # Build classification with explicit None for missing fields
            # (like seed_generic_factors.py - don't rely on validated DTO)
            classification: dict[str, Any] = {}
            for field_name in handler.classification_fields:
                value = row.get(field_name)
                classification[field_name] = (
                    value.strip() if value and value.strip() else None
                )

            # Build values with type conversion, filtering empty values
            values: dict[str, Any] = {}
            for field_name in handler.value_fields:
                value = row.get(field_name)
                if value and str(value).strip():
                    converted = self._convert_value(value)
                    values[field_name] = converted

            # #2091: an unmappable emission type aborts the upload instead
            # of skipping the row. Skipping commits every *other* row, so the
            # factor table ends up half-updated and the module quietly loses
            # a category — the failure the operator never sees. Malformed
            # values (bad float, missing column) keep their skip semantics
            # below; only emission-type resolution escalates.
            emission_type_id = get_factor_emission_type_id(
                data_entry_type, classification
            )

            # Validate the payload (ensures data types are correct)
            # but use our manually built classification/values dicts
            validation_payload: dict[str, Any] = {
                **classification,
                **values,
                "data_entry_type_id": data_entry_type.value,
                "emission_type_id": emission_type_id,
            }

            try:
                handler.validate_create(validation_payload)
            except ValidationError as validation_error:
                error_msg = _format_pydantic_validation_error(validation_error)
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg
            except Exception as validation_error:
                error_msg = f"Validation error: {validation_error}"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, error_msg

            # ``year`` is stored on the dedicated ``Factor.year`` column;
            # do NOT also inject it into ``classification``.  The Plan 310B
            # identity index keys on ``(det, year, emission_type,
            # classification::text)`` — duplicating ``year`` inside
            # ``classification`` would silently shift the
            # ``classification::text`` representation between writers and
            # break the upsert's identity match.
            factor = await factor_service.prepare_create(
                emission_type_id=emission_type_id,
                data_entry_type_id=data_entry_type.value,
                classification=classification,
                values=values,
                year=self.year,
            )
            return factor, None
        except EmissionTypeResolutionError as resolution_error:
            raise EmissionTypeResolutionError(
                f"Row {row_idx}: {resolution_error}"
            ) from resolution_error
        except Exception as row_error:
            logger.error(f"Row {row_idx}: Error processing row: {str(row_error)}")
            error_msg = f"Row processing error: {row_error}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, error_msg

    def _resolve_data_entry_type(
        self,
        row: dict[str, str],
        setup_result: dict[str, Any],
        row_idx: int,
        stats: FactorStatsDict,
        max_row_errors: int,
    ) -> DataEntryTypeEnum | None:
        """Resolve data_entry_type with priority:
        1. Configured data_entry_type_id
        2. Handler's category_field (e.g., equipment_category)
        """
        configured = self.data_entry_type_id
        if configured is not None:
            return DataEntryTypeEnum(int(configured))

        # Try to resolve from handler's category_field
        # Get handlers from setup_result
        handlers = setup_result.get("handlers", [])
        # because for purchases or other types we might have multiple handlers,
        # we need to check each one for its category field and see if
        # it matches the CSV row

        for handler in handlers:
            if not hasattr(handler, "category_field"):
                continue
            category_field = getattr(handler, "category_field", None)
            if category_field and category_field in row:
                category_value = row.get(category_field, "").strip()
                if category_value:
                    try:
                        # Case-sensitive: the category column (e.g.
                        # equipment_category) must match a DataEntryTypeEnum
                        # member name exactly (doc: {scientific,it,other}).
                        return DataEntryTypeEnum[category_value]
                    except KeyError:
                        error_msg = f"Invalid {category_field}: {category_value}"
                        self._record_row_error(
                            stats, row_idx, error_msg, max_row_errors
                        )
                        return None
        # If we can't resolve, record error
        error_msg = "Missing data_entry_type_id in config or category field in CSV"
        self._record_row_error(stats, row_idx, error_msg, max_row_errors)
        return None

    async def _process_batch(
        self,
        batch: list[Factor],
        factor_service: FactorService,
    ) -> None:
        # Legacy path retained for subclasses that override (notably
        # ``LocalFactorCSVProvider`` which does delete-and-insert for dev
        # seeding). Production factor ingest goes through ``_upsert_batch``.
        await factor_service.bulk_create(batch)
        logger.info(f"Created {len(batch)} factors in batch")

    async def _upsert_batch(
        self,
        batch: list[Factor],
        factor_repo: FactorRepository,
    ) -> int:
        """Upsert one batch keyed on the factor identity index.

        Returns the number of rows affected so callers can update stats.
        Requires ``self.job_id`` so each upserted row can be stamped with
        ``last_seen_job_id``.
        """
        if self.job_id is None:
            raise ValueError("job_id is required for factor upsert")
        affected = await factor_repo.upsert_factors(batch, current_job_id=self.job_id)
        self._upserted_det_ids.update(f.data_entry_type_id for f in batch)
        # asyncpg can return rowcount=-1 for executemany ON CONFLICT
        # statements where it can't tally the result reliably.  Fall back
        # to the input batch size for stats so the operator-visible count
        # isn't a confusing -1.
        reported = affected if affected >= 0 else len(batch)
        logger.info(f"Upserted {reported} factors in batch of {len(batch)}")
        return reported

    def _compute_ingestion_result(self, stats: FactorStatsDict) -> IngestionResult:
        """Compute ingestion result based on success rate.

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
        batch: list[Factor],
        factor_service: FactorService,
        stats: FactorStatsDict,
        setup_result: dict[str, Any],
        factor_repo: FactorRepository,
    ) -> dict[str, Any]:
        if batch:
            upserted = await self._upsert_batch(batch, factor_repo)
            stats["factors_upserted"] += upserted

        result = self._compute_ingestion_result(stats)
        # Sweep only on full SUCCESS: a partial upload (WARNING) failed to
        # re-ingest some rows, and deleting the factors those rows would
        # have refreshed silently destroys data on operator error. The
        # operator re-uploads a corrected CSV; that SUCCESS run sweeps.
        if result == IngestionResult.SUCCESS:
            stats["factors_deleted"] = await self._delete_stale_factors(factor_repo)

        processing_path = setup_result["processing_path"]
        metadata_update: dict[str, Any] = {
            "processed_file_path": await self._move_to_processed(processing_path)
        }

        await self.data_session.flush()

        status_message = (
            f"Processed {stats['rows_processed']} rows: "
            f"{stats['rows_skipped']} skipped, "
            f"{stats['row_errors_count']} errors, "
            f"{stats['factors_upserted']} factors upserted, "
            f"{stats['factors_deleted']} factors deleted"
        )

        metadata_for_job = {k: v for k, v in stats.items() if k != "row_errors"}
        metadata_for_job["stats"] = stats
        metadata_for_job.update(metadata_update)
        await self._update_job(
            status_message=status_message,
            state=IngestionState.FINISHED,
            result=result,
            extra_metadata=metadata_for_job,
        )

        logger.info(
            f"CSV processing completed: {stats['rows_processed']} rows processed, "
            f"{stats['rows_skipped']} skipped, "
            f"{stats['row_errors_count']} errors, "
            f"{stats['factors_upserted']} factors upserted, "
            f"{stats['factors_deleted']} factors deleted"
        )
        return {
            "state": IngestionState.FINISHED,
            "result": result,
            "inserted": stats["rows_processed"],
            "skipped": stats["rows_skipped"],
            "stats": stats,
        }

    async def _derive_dependent_factors(self, result: dict[str, Any]) -> None:
        """Refresh factors that are averages of the ones this upload carried.

        The planner's purchase factors are one such: they exist so a plan can
        price a budget, and they are only correct while they match the
        Calculator factors they average — so they are rebuilt here, in the
        upload's own transaction, rather than maintained apart.

        Skipped on a partial upload: averaging a set where some rows are the
        new upload's and some are the previous one's publishes a number that
        matches neither.
        """
        if result["result"] != IngestionResult.SUCCESS or self.year is None:
            return
        # What the rows actually carried, not what the module allows: the
        # centralized-purchases CSV is valid for the same module and prices
        # none of the categories these averages are taken over.
        if self._upserted_det_ids & {det.value for det in PURCHASE_SOURCE_TYPES}:
            await derive_planner_purchase_factors(
                self.data_session, self.year, self.job_id
            )

    async def _delete_stale_factors(self, factor_repo: FactorRepository) -> int:
        """Delete factors this job's upsert just superseded.

        Runs in the same transaction as the upsert, before the handler's
        stale-recalc fan-out (``_chain_recalc_for_stale`` in
        ``ingestion_tasks.py``) dispatches — so the cascade-deleted
        emission rows are part of the same commit the fan-out reads
        from.  Scope is the dets this job actually upserted, not the
        module's full coverage — an upload replaces exactly what it
        carries.

        See ``delete_stale_for_year`` for why the threshold is this
        job's id rather than a job-state lookup.
        """
        if self.year is None or self.job_id is None:
            raise ValueError(
                "_delete_stale_factors requires year and job_id; "
                "run() assigns both before any row is processed"
            )
        if not self._upserted_det_ids:
            return 0
        return await factor_repo.delete_stale_for_year(
            self.year,
            det_ids=sorted(self._upserted_det_ids),
            threshold_job_id=self.job_id,
        )

    @abstractmethod
    async def _setup_handlers_and_context(self) -> dict[str, Any]:
        pass

    @staticmethod
    def _convert_value(value: str | None) -> float | int | str | None:
        """Convert CSV value to appropriate type."""
        if value is None or str(value).strip() == "":
            return None
        value = str(value).strip()
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def _get_types_to_delete(
        self, listed_entry_types: list[DataEntryTypeEnum]
    ) -> list[DataEntryTypeEnum]:
        """Return the data entry types whose factors should be deleted before ingestion.

        Override in subclasses to restrict deletion to a subset of types
        (e.g. when a CSV covers only part of a module's types).
        """
        if self.data_entry_type_id is not None:
            return [DataEntryTypeEnum(int(self.data_entry_type_id))]
        return list(listed_entry_types)

    def _record_row_error(
        self,
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
        """Resolve valid data entry types for this ingestion job."""
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
