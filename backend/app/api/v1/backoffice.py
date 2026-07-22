"""Backoffice API endpoints."""

import csv
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, List, NamedTuple, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.constants import (
    DEFAULT_CARBON_FOOTPRINT,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE_EXPORT,
    DEFAULT_PAGE_SIZE_UNITS,
    ERROR_AT_LEAST_ONE_YEAR,
    ERROR_INVALID_FORMAT,
    EXPORT_CSV_DATE_FORMAT,
    EXPORT_CSV_HEADERS,
    EXPORT_CSV_TIMESTAMP_FORMAT,
    EXPORT_FILENAME_PREFIX_DETAILED,
    EXPORT_FILENAME_PREFIX_REPORTING,
    EXPORT_FILENAME_PREFIX_RESULTS,
    EXPORT_FILENAME_PREFIX_USAGE,
    MAX_PAGE_SIZE_EXPORT,
    MAX_PAGE_SIZE_UNITS,
    MIN_PAGE_SIZE,
    STATUS_TO_ENUM,
    UNKNOWN_AFFILIATION,
    UNKNOWN_STATUS,
    UNKNOWN_UNIT,
    UNKNOWN_USER,
    YEAR_LENGTH,
    ModuleStatus,
)
from app.core.logging import get_logger
from app.core.security import get_current_active_user, require_permission
from app.models.carbon_report import (
    CarbonReport,
    CarbonReportModule,
)
from app.models.data_entry import (
    DataEntry,
    DataEntrySourceEnum,
    DataEntryTypeEnum,
)
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.module_type import (
    DEFAULT_COMPLETION_PROGRESS,
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    get_module_type_for_data_entry_type,
)
from app.models.unit import Unit
from app.models.user import User
from app.repositories.carbon_report_module_repo import (
    CarbonReportModuleRepository,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.repositories.factor_repo import FactorRepository
from app.schemas.backoffice import (
    BulkDeleteResponse,
    PaginatedBackofficeFactors,
    PaginatedUnitReportingData,
    PaginationMeta,
    UnitReportingData,
)
from app.schemas.factor import BaseFactorHandler
from app.schemas.user import UserRead
from app.services.data_entry_service import DataEntryService
from app.tasks._background import fire_and_forget
from app.tasks.runner import run_job
from app.utils.scoping import (
    build_scope_subtree_predicate,
    gate_backoffice,
)

logger = get_logger(__name__)
router = APIRouter()


class BackofficeFilters(NamedTuple):
    """Unified filter parameters for all backoffice reporting endpoints."""

    path_affiliation: Optional[List[str]]
    path_lvl4: Optional[List[str]]
    overall_status: Optional[ModuleStatus]
    search: Optional[str]
    modules: Optional[List[str]]
    years: Optional[List[int]]


def get_backoffice_filters(
    path_affiliation: Optional[List[str]] = Query(
        None,
        description=(
            "Filter by affiliations (Faculties, Services, Institutes). "
            "Returns all descendant units of selected affiliations."
        ),
    ),
    path_lvl4: Optional[List[str]] = Query(
        None,
        description=(
            "Filter by specific unit names or IDs (Level 4). "
            "Returns exact matches only (not descendants)."
        ),
    ),
    overall_status: Optional[ModuleStatus] = Query(
        None,
        description=(
            "Filter by report overall status: NOT_STARTED (0), IN_PROGRESS (1), "
            "VALIDATED (2)"
        ),
    ),
    search: Optional[str] = Query(
        None,
        description="Search in unit name, affiliation path, or principal user name",
    ),
    modules: Optional[List[str]] = Query(
        None,
        description=(
            "Filter by module states, format: 'module_name:state' "
            "(e.g., 'headcount:validated')"
        ),
    ),
    years: Optional[List[int]] = Query(
        None, description="Filter by specific years (e.g., [2024, 2025])"
    ),
) -> BackofficeFilters:
    """Dependency providing unified backoffice filter parameters."""
    return BackofficeFilters(
        path_affiliation=path_affiliation,
        path_lvl4=path_lvl4,
        overall_status=overall_status,
        search=search,
        modules=modules,
        years=years,
    )


def get_module_status(module_data: dict | str) -> str:
    """Extract status from module data
    (handles both old string format and new object format)."""
    if isinstance(module_data, dict):
        return module_data.get("status", "not_started")
    return module_data if isinstance(module_data, str) else "not_started"


def get_module_outlier_values(module_data: dict | str) -> int:
    """
    Extract outlier_values from module data
    (handles both old string format and new object format).
    """
    if isinstance(module_data, dict):
        return module_data.get("outlier_values", 0)
    return 0


def _is_year_based(completion: dict) -> bool:
    """Check if completion data is year-based (has year keys like '2024', '2025')."""
    return any(
        isinstance(key, str) and key.isdigit() and len(key) == YEAR_LENGTH
        for key in completion.keys()
    )


def _get_year_keys(completion: dict) -> list[str]:
    """Extract all year keys from completion data."""
    return [
        k
        for k in completion.keys()
        if isinstance(k, str) and k.isdigit() and len(k) == YEAR_LENGTH
    ]


def _get_years_to_process(
    completion: dict, years: list[str] | None = None
) -> list[str]:
    """
    Get list of years to process
    defaulting to all available years if none specified.
    """
    if years:
        year_keys = set(_get_year_keys(completion))
        return [str(y).strip() for y in years if str(y).strip() in year_keys]
    return _get_year_keys(completion)


def get_completion_for_years(completion: dict, years: list[str] | None = None) -> dict:
    """
    Extract completion data for selected years.
    If years is None or empty, returns all years aggregated.
    If completion is old format (no years), returns it as-is.
    """
    if not _is_year_based(completion):
        return completion

    years_to_process = _get_years_to_process(completion, years)
    aggregated: dict[str, dict[str, Any]] = {}

    for year in years_to_process:
        year_data = completion.get(year, {})
        if not isinstance(year_data, dict):
            continue

        for module_name, module_data in year_data.items():
            existing_module = aggregated.get(module_name)
            current_status = get_module_status(
                existing_module if existing_module else {}
            )
            new_status = get_module_status(module_data)
            new_outlier = get_module_outlier_values(module_data)

            if module_name not in aggregated:
                aggregated[module_name] = {
                    "status": new_status,
                    "outlier_values": new_outlier,
                }
            else:
                # Use best status, sum outlier values
                if STATUS_TO_ENUM.get(
                    new_status, ModuleStatus.NOT_STARTED
                ) > STATUS_TO_ENUM.get(current_status, ModuleStatus.NOT_STARTED):
                    aggregated[module_name]["status"] = new_status
                current_outlier = aggregated[module_name].get("outlier_values", 0)
                if isinstance(current_outlier, int):
                    aggregated[module_name]["outlier_values"] = (
                        current_outlier + new_outlier
                    )

    return aggregated


@router.get("/units", response_model=PaginatedUnitReportingData)
async def list_backoffice_units(
    filters: BackofficeFilters = Depends(get_backoffice_filters),
    page: int = Query(
        DEFAULT_PAGE, ge=MIN_PAGE_SIZE, description="Page number for pagination"
    ),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE_UNITS,
        ge=0,
        le=MAX_PAGE_SIZE_UNITS,
        description="Number of items per page (0 for all items)",
    ),
    sort_by: Optional[str] = Query(
        None,
        description=(
            "Field to sort by: unit_name, affiliation, validation_status, "
            "principal_user, last_update, highest_result_category, "
            "total_carbon_footprint"
        ),
    ),
    sort_order: Optional[str] = Query(
        None,
        description="Sort order: 'asc' for ascending, 'desc' for descending",
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List units with their reporting completion status and outlier values.
    """
    is_global, affiliations = gate_backoffice(current_user, "view")
    # Scoped caller with no granted affiliations → nothing to see.
    if not is_global and not affiliations:
        return PaginatedUnitReportingData(
            data=[],
            pagination=PaginationMeta(
                total=0, page=page, page_size=page_size, total_pages=0
            ),
            validated_units_count=0,
            in_progress_units_count=0,
            not_started_units_count=0,
            total_units_count=0,
        )

    carbon_report_module_repo = CarbonReportModuleRepository(db)

    if filters.years is None or len(filters.years) == 0:
        raise HTTPException(status_code=400, detail=ERROR_AT_LEAST_ONE_YEAR)

    result = await carbon_report_module_repo.get_reporting_overview(
        path_affiliation=filters.path_affiliation,
        path_lvl4=filters.path_lvl4,
        is_global=is_global,
        scope_cfs=affiliations,
        overall_status=filters.overall_status,
        search=filters.search,
        modules=filters.modules,
        years=filters.years,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    # Convert the data to UnitReportingData instances
    unit_reporting_data = []
    for item in result.get("data", []):
        if isinstance(item, dict):
            completion = item.get("completion_progress", DEFAULT_COMPLETION_PROGRESS)
            overall_status = ModuleStatus.NOT_STARTED
            left, right = completion.split("/")
            if left == right and left != "0":
                overall_status = ModuleStatus.VALIDATED
            elif left != "0":
                overall_status = ModuleStatus.IN_PROGRESS
            unit_reporting_data.append(
                UnitReportingData(
                    id=item.get("id", -1),
                    unit_name=item.get("unit_name", UNKNOWN_UNIT),
                    affiliation=item.get("affiliation", UNKNOWN_AFFILIATION),
                    validation_status=item.get("validation_status", UNKNOWN_STATUS),
                    principal_user=item.get("principal_user", UNKNOWN_USER),
                    last_update=item.get("last_update"),
                    highest_result_category=item.get("highest_result_category"),
                    total_carbon_footprint=item.get(
                        "total_carbon_footprint", DEFAULT_CARBON_FOOTPRINT
                    ),
                    total_fte=item.get("total_fte"),
                    view_url=item.get("view_url"),
                    completion=overall_status,
                    completion_progress=item.get("completion_progress"),
                )
            )
        elif isinstance(item, CarbonReport):
            unit_reporting_data.append(UnitReportingData.model_validate(item))
        else:
            unit_reporting_data.append(item)

    return PaginatedUnitReportingData(
        data=unit_reporting_data,
        pagination=PaginationMeta(**result),
        stats=result.get("stats"),
        validated_units_count=result.get("validated_units_count", 0),
        in_progress_units_count=result.get("in_progress_units_count", 0),
        not_started_units_count=result.get("not_started_units_count", 0),
        total_units_count=result.get("total_units_count", 0),
        module_status_counts=result.get("module_status_counts"),
    )


@router.get("/export")
async def export_reporting(
    filters: BackofficeFilters = Depends(get_backoffice_filters),
    format: str = Query("csv", description="Export format: csv or json"),
    page: int = Query(
        DEFAULT_PAGE, ge=MIN_PAGE_SIZE, description="Page number for pagination"
    ),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE_EXPORT,
        ge=MIN_PAGE_SIZE,
        le=MAX_PAGE_SIZE_EXPORT,
        description="Number of items per page",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export unit reporting data as CSV or JSON file download."""
    gate_backoffice(current_user, "export")
    # Get all matching records for export. The inner ``list_backoffice_units``
    # applies the affiliation narrowing via its own ``gate_backoffice("view")``.
    reporting_data = await list_backoffice_units(
        filters=filters,
        page=page,
        page_size=page_size,
        current_user=current_user,
        db=db,
    )
    today = datetime.now(timezone.utc).strftime(EXPORT_CSV_DATE_FORMAT)

    if format == "json":
        # JSON export
        export_data = [doc.model_dump() for doc in reporting_data.data]

        content = json.dumps(export_data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f"attachment; filename="
                    f'"{EXPORT_FILENAME_PREFIX_REPORTING}_{today}.json"'
                ),
            },
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(EXPORT_CSV_HEADERS)

        for doc in reporting_data.data:
            writer.writerow(
                [
                    doc.id,
                    doc.unit_name,
                    doc.affiliation,
                    doc.validation_status,
                    doc.principal_user,
                    doc.last_update.isoformat() if doc.last_update else "",
                    doc.highest_result_category or "",
                    doc.total_carbon_footprint,
                    doc.view_url or "",
                ]
            )

        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f"attachment; filename="
                    f'"{EXPORT_FILENAME_PREFIX_REPORTING}_{today}.csv"'
                ),
            },
        )


@router.get("/years")
async def get_available_years(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all available years from CarbonReport records in the database,
    sorted in descending order (latest first).

    Affiliation-scoped backoffice users see only the years where reports
    exist for units inside their scope subtree (#862).
    """
    is_global, affiliations = gate_backoffice(current_user, "view")
    stmt = select(CarbonReport.year).distinct()
    if not is_global:
        if not affiliations:
            return {"years": [], "latest": ""}
        stmt = stmt.join(Unit, col(CarbonReport.unit_id) == col(Unit.id)).where(
            build_scope_subtree_predicate(affiliations)
        )
    stmt = stmt.order_by(desc(CarbonReport.year))
    result = await db.exec(stmt)
    years = [str(y) for y in result.all()]
    if not years:
        return {"years": [], "latest": ""}
    return {"years": years, "latest": years[0]}


@router.get("/report/usage")
async def report_usage(
    filters: BackofficeFilters = Depends(get_backoffice_filters),
    format: str = Query("csv", description="Export format: csv or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail=ERROR_INVALID_FORMAT)

    is_global, affiliations = gate_backoffice(current_user, "export")
    if not is_global and not affiliations:
        data = []
    else:
        try:
            data = await CarbonReportModuleRepository(db).get_usage_report(
                path_affiliation=filters.path_affiliation,
                path_lvl4=filters.path_lvl4,
                is_global=is_global,
                scope_cfs=affiliations,
                overall_status=filters.overall_status,
                search=filters.search,
                modules=filters.modules,
                years=filters.years,
            )
        except ValueError as exc:
            # Invalid filter values or other issues in query parameters
            raise HTTPException(status_code=400, detail=str(exc))

    timestamp = datetime.now(timezone.utc).strftime(EXPORT_CSV_TIMESTAMP_FORMAT)
    if format == "json":
        content = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f"attachment; filename="
                    f'"{EXPORT_FILENAME_PREFIX_USAGE}_{timestamp}.json"'
                ),
            },
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        if data:
            # Build a stable header list across all rows to avoid misalignment
            headers: list[str] = []
            for row in data:
                for key in row.keys():
                    if key not in headers:
                        headers.append(key)
            writer.writerow(headers)
            for row in data:
                writer.writerow([row.get(h, "") for h in headers])
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f"attachment; filename="
                    f'"{EXPORT_FILENAME_PREFIX_USAGE}_{timestamp}.csv"'
                ),
            },
        )


@router.get("/report/detailed")
async def report_detailed(
    filters: BackofficeFilters = Depends(get_backoffice_filters),
    format: str = Query("csv", description="Export format: csv or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail=ERROR_INVALID_FORMAT)

    is_global, affiliations = gate_backoffice(current_user, "export")
    scoped_caller_no_affiliations = not is_global and not affiliations

    timestamp = datetime.now(timezone.utc).strftime(EXPORT_CSV_TIMESTAMP_FORMAT)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for data_entry_types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.values():
            for data_entry_type in data_entry_types:
                if scoped_caller_no_affiliations:
                    continue
                try:
                    data = await CarbonReportModuleRepository(db).get_detailed_report(
                        data_entry_type=data_entry_type,
                        path_affiliation=filters.path_affiliation,
                        path_lvl4=filters.path_lvl4,
                        is_global=is_global,
                        scope_cfs=affiliations,
                        overall_status=filters.overall_status,
                        search=filters.search,
                        modules=filters.modules,
                        years=filters.years,
                    )
                except ValueError as exc:
                    # Invalid filter values or other issues in query parameters
                    raise HTTPException(status_code=400, detail=str(exc))

                if data is None or len(data) == 0:
                    continue

                file_path = tmp_path / f"{data_entry_type.name}.{format}"
                if format == "json":
                    file_path.write_text(
                        json.dumps(data, indent=2, default=str), encoding="utf-8"
                    )
                else:
                    with open(file_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        # Build a stable header list across all rows to avoid
                        # misalignment
                        headers: list[str] = []
                        for row in data:
                            for key in row.keys():
                                if key not in headers:
                                    headers.append(key)
                        writer.writerow(headers)
                        for row in data:
                            writer.writerow([row.get(h, "") for h in headers])

        zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(zip_fd)
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in sorted(tmp_path.iterdir()):
                    zip_file.write(file_path, file_path.name)
        except Exception:
            os.unlink(zip_path)
            raise

    def _stream_and_cleanup() -> Generator[bytes, None, None]:
        try:
            with open(zip_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk
        finally:
            os.unlink(zip_path)

    return StreamingResponse(
        _stream_and_cleanup(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; "
            f'filename="{EXPORT_FILENAME_PREFIX_DETAILED}_{timestamp}.zip"'
        },
    )


@router.get("/report/results")
async def report_results(
    filters: BackofficeFilters = Depends(get_backoffice_filters),
    format: str = Query("csv", description="Export format: csv or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail=ERROR_INVALID_FORMAT)

    is_global, affiliations = gate_backoffice(current_user, "export")
    if not is_global and not affiliations:
        data = []
    else:
        try:
            data = await CarbonReportModuleRepository(db).get_results_report(
                path_affiliation=filters.path_affiliation,
                path_lvl4=filters.path_lvl4,
                is_global=is_global,
                scope_cfs=affiliations,
                overall_status=filters.overall_status,
                search=filters.search,
                years=filters.years,
            )
        except ValueError as exc:
            # Invalid filter values or other issues in query parameters
            raise HTTPException(status_code=400, detail=str(exc))

    timestamp = datetime.now(timezone.utc).strftime(EXPORT_CSV_TIMESTAMP_FORMAT)
    if format == "json":
        content = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f"attachment; filename="
                    f'"{EXPORT_FILENAME_PREFIX_RESULTS}_{timestamp}.json"'
                ),
            },
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        if data:
            # Build a stable header list across all rows to avoid misalignment
            headers: list[str] = []
            for row in data:
                for key in row.keys():
                    if key not in headers:
                        headers.append(key)
            writer.writerow(headers)
            for row in data:
                writer.writerow([row.get(h, "") for h in headers])
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f"attachment; filename="
                    f'"{EXPORT_FILENAME_PREFIX_RESULTS}_{timestamp}.csv"'
                ),
            },
        )


# ---------------------------------------------------------------------------
# Factor & data-entry management (#1491)
# ---------------------------------------------------------------------------


def _parse_data_entry_type(data_entry_type_id: int) -> DataEntryTypeEnum:
    try:
        return DataEntryTypeEnum(data_entry_type_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown data_entry_type_id: {data_entry_type_id}",
        )


async def _dispatch_emission_recalc(
    db: AsyncSession,
    *,
    data_entry_type: DataEntryTypeEnum,
    year: int,
    user: User,
    carbon_report_module_id: Optional[int] = None,
) -> tuple[Optional[int], Optional[str]]:
    """Dispatch a root ``emission_recalc`` job for the deleted scope.

    A bulk delete changes operator-owned state (factors / data entries);
    emissions and the stat buckets (``carbon_report_module.stats``) are
    derived from it.  The ``emission_recalc`` handler rebuilds the
    ``(data_entry_type, year)`` emission slice and chains the trailing
    ``aggregation`` that rewrites the stat buckets — the same path every
    ingest uses, so the system converges to the state a re-upload would
    produce.  The admin ``recompute-stats`` trigger is NOT sufficient
    here: it re-aggregates existing emission rows without rebuilding
    them (and is designed for unchanged data — it skips the module
    status bump), so emission rows left behind by a factor delete would
    keep feeding stale numbers into the stats.

    Mirrors ``recalculate_emissions_for_type`` in ``data_sync.py``.
    Returns ``(job_id, pipeline_id)``.
    """
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if module_type is None:
        # Without a module type the recalc's advisory lock and the
        # chained aggregation have no scope — surface loudly instead of
        # leaving stats silently stale.
        raise HTTPException(
            status_code=500,
            detail=(
                f"No module type mapped for data_entry_type "
                f"{data_entry_type.name}; cannot chain recalculation"
            ),
        )

    config: dict[str, Any] = {
        "year": year,
        "data_entry_type_id": data_entry_type.value,
    }
    if carbon_report_module_id is not None:
        # Module-scoped delete → module-scoped recalc (same pinning the
        # unit-specific ingest does), so a small delete doesn't recompute
        # the whole (det, year) slice.
        config["carbon_report_module_ids"] = [carbon_report_module_id]

    pipeline_id = uuid4()
    job = DataIngestionJob(
        job_type="emission_recalc",
        module_type_id=module_type.value,
        data_entry_type_id=data_entry_type.value,
        year=year,
        ingestion_method=IngestionMethod.computed,
        target_type=TargetType.DATA_ENTRIES,
        entity_type=EntityType.MODULE_PER_YEAR,
        state=IngestionState.NOT_STARTED,
        provider=user.provider,
        pipeline_id=pipeline_id,
        meta={"config": config},
    )
    repo = DataIngestionRepository(db)
    await repo.ensure_pipeline_exists(
        pipeline_id,
        kind="emission_recalc",
        entity_type=EntityType.MODULE_PER_YEAR.value,
        ingestion_method=IngestionMethod.computed.value,
        module_type_id=module_type.value,
        year=year,
    )
    created_job = await repo.create_ingestion_job(job)
    await db.commit()
    if created_job.id is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to create recalculation job",
        )
    fire_and_forget(run_job(created_job.id), name=f"run_job-{created_job.id}")
    return created_job.id, str(pipeline_id)


@router.get("/factors", response_model=PaginatedBackofficeFactors)
async def list_backoffice_factors(
    data_entry_type_id: int = Query(..., description="DataEntryTypeEnum value"),
    year: int = Query(..., description="Factor year scope"),
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.configuration", "view")
    ),
) -> PaginatedBackofficeFactors:
    """Paginated factor viewer for one ``(data_entry_type, year)`` scope.

    Rows are serialized through the type's factor handler and carry
    ``last_seen_job_id`` so an operator can spot rows the latest upload
    did not assert (#1491).
    """
    det = _parse_data_entry_type(data_entry_type_id)
    try:
        handler = BaseFactorHandler.get_by_type(det)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    repo = FactorRepository(db)
    total = await repo.count_by_data_entry_type_and_year(det.value, year)
    factors = await repo.list_by_data_entry_type(
        det, year, limit=page_size, offset=(page - 1) * page_size
    )
    data = [
        {
            **handler.to_response(factor).model_dump(),
            "year": factor.year,
            "last_seen_job_id": factor.last_seen_job_id,
        }
        for factor in factors
    ]
    return PaginatedBackofficeFactors(
        data=data,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=-(-total // page_size) if total else 0,
        ),
    )


@router.delete("/factors", response_model=BulkDeleteResponse)
async def bulk_delete_backoffice_factors(
    data_entry_type_id: int = Query(..., description="DataEntryTypeEnum value"),
    year: int = Query(..., description="Factor year scope"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.configuration", "edit")
    ),
) -> BulkDeleteResponse:
    """Bulk delete every factor of one ``(data_entry_type, year)`` scope.

    Emission rows referencing the factors go via FK CASCADE; an
    ``emission_recalc`` is dispatched so surviving entries are rebuilt
    against what remains and the stat buckets are re-aggregated (#1491).
    """
    det = _parse_data_entry_type(data_entry_type_id)
    repo = FactorRepository(db)
    factor_ids = await repo.list_id_by_data_entry_type_and_year(det, year)
    if not factor_ids:
        return BulkDeleteResponse(deleted=0)

    await repo.bulk_delete(factor_ids)
    await db.commit()
    logger.info(
        f"backoffice: deleted {len(factor_ids)} factors for "
        f"det={det.name}/year={year} (user {current_user.id})"
    )
    job_id, pipeline_id = await _dispatch_emission_recalc(
        db, data_entry_type=det, year=year, user=current_user
    )
    return BulkDeleteResponse(
        deleted=len(factor_ids),
        recalc_job_id=job_id,
        recalc_pipeline_id=pipeline_id,
    )


@router.delete("/data-entries", response_model=BulkDeleteResponse)
async def bulk_delete_backoffice_data_entries(
    data_entry_type_id: int = Query(..., description="DataEntryTypeEnum value"),
    source: int = Query(..., description="DataEntrySourceEnum value"),
    year: int = Query(..., description="Report year"),
    carbon_report_module_id: Optional[int] = Query(
        None,
        description="Restrict to one carbon report module; omit for the whole year",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_permission("backoffice.configuration", "edit")
    ),
) -> BulkDeleteResponse:
    """Bulk delete data entries by type + source, year- or module-scoped.

    Deleted entries' emission rows go via FK CASCADE; an
    ``emission_recalc`` (module-scoped when the delete was) is dispatched
    so the stat buckets are re-aggregated (#1491).
    """
    det = _parse_data_entry_type(data_entry_type_id)
    try:
        source_enum = DataEntrySourceEnum(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    service = DataEntryService(db)
    if carbon_report_module_id is not None:
        # The module pins the year — reject a mismatched year param so the
        # chained recalc can't target the wrong slice.
        module_year_stmt = (
            select(CarbonReport.year)
            .join(
                CarbonReportModule,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .where(col(CarbonReportModule.id) == carbon_report_module_id)
        )
        module_year = (await db.execute(module_year_stmt)).scalar_one_or_none()
        if module_year is None:
            raise HTTPException(
                status_code=404,
                detail=f"Carbon report module {carbon_report_module_id} not found",
            )
        if module_year != year:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Module {carbon_report_module_id} belongs to year "
                    f"{module_year}, not {year}"
                ),
            )
        count_stmt = (
            select(func.count())
            .select_from(DataEntry)
            .where(
                col(DataEntry.carbon_report_module_id) == carbon_report_module_id,
                col(DataEntry.data_entry_type_id) == det.value,
                col(DataEntry.source) == source_enum.value,
            )
        )
        deleted = (await db.execute(count_stmt)).scalar_one()
        if deleted:
            await service.bulk_delete_by_source(
                carbon_report_module_id,
                det,
                source_enum.value,
                user=UserRead.model_validate(current_user, from_attributes=True),
            )
    else:
        deleted = await service.repo.bulk_delete_by_source_year(
            year, [det.value], source_enum.value
        )

    if not deleted:
        return BulkDeleteResponse(deleted=0)

    await db.commit()
    logger.info(
        f"backoffice: deleted {deleted} data entries for det={det.name}/"
        f"source={source_enum.name}/year={year}"
        f"/module={carbon_report_module_id} (user {current_user.id})"
    )
    job_id, pipeline_id = await _dispatch_emission_recalc(
        db,
        data_entry_type=det,
        year=year,
        user=current_user,
        carbon_report_module_id=carbon_report_module_id,
    )
    return BulkDeleteResponse(
        deleted=deleted,
        recalc_job_id=job_id,
        recalc_pipeline_id=pipeline_id,
    )
