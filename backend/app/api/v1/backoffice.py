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

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import desc, select
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
    STATUS_ORDER,
    UNKNOWN_AFFILIATION,
    UNKNOWN_STATUS,
    UNKNOWN_UNIT,
    UNKNOWN_USER,
    YEAR_LENGTH,
    ModuleStatus,
)
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.carbon_report import (
    CarbonReport,
)
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES
from app.models.user import User
from app.repositories.carbon_report_module_repo import (
    CarbonReportModuleRepository,
)
from app.schemas.backoffice import (
    PaginatedUnitReportingData,
    PaginationMeta,
    UnitReportingData,
)

logger = get_logger(__name__)
router = APIRouter()


class BackofficeFilters(NamedTuple):
    """Unified filter parameters for all backoffice reporting endpoints."""

    path_affiliation: Optional[List[str]]
    path_lvl4: Optional[List[str]]
    completion_status: Optional[ModuleStatus]
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
    completion_status: Optional[ModuleStatus] = Query(
        None,
        description=(
            "Filter by completion status: NOT_STARTED (0), IN_PROGRESS (1), "
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
        completion_status=completion_status,
        search=search,
        modules=modules,
        years=years,
    )


def get_module_status(module_data: dict | str) -> str:
    """Extract status from module data
    (handles both old string format and new object format)."""
    if isinstance(module_data, dict):
        return module_data.get("status", "default")
    return module_data if isinstance(module_data, str) else "default"


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
                if STATUS_ORDER.get(new_status, 0) > STATUS_ORDER.get(
                    current_status, 0
                ):
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
        ge=MIN_PAGE_SIZE,
        le=MAX_PAGE_SIZE_UNITS,
        description="Number of items per page",
    ),
    current_user: User = Depends(require_permission("backoffice.users", "view")),
    db: AsyncSession = Depends(get_db),
):
    """
    List units with their reporting completion status and outlier values.
    """
    carbon_report_module_repo = CarbonReportModuleRepository(db)

    if filters.years is None or len(filters.years) == 0:
        raise HTTPException(status_code=400, detail=ERROR_AT_LEAST_ONE_YEAR)

    result = await carbon_report_module_repo.get_reporting_overview(
        path_affiliation=filters.path_affiliation,
        path_lvl4=filters.path_lvl4,
        completion_status=filters.completion_status,
        search=filters.search,
        modules=filters.modules,
        years=filters.years,
        page=page,
        page_size=page_size,
    )
    # Convert the data to UnitReportingData instances
    unit_reporting_data = []
    for item in result.get("data", []):
        if isinstance(item, dict):
            completion = item.get("completion_progress", "0/8")
            completion_status = ModuleStatus.NOT_STARTED
            left, right = completion.split("/")
            if left == right and left != "0":
                completion_status = ModuleStatus.VALIDATED
            elif left != "0":
                completion_status = ModuleStatus.IN_PROGRESS
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
                    completion=completion_status,
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
        emission_breakdown=result.get("emission_breakdown"),
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
    current_user: User = Depends(require_permission("backoffice.users", "export")),
):
    """Export unit reporting data as CSV or JSON file download."""
    # Get all matching records for export
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
    current_user: User = Depends(require_permission("backoffice.users", "view")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all available years from CarbonReport records in the database,
    sorted in descending order (latest first).
    """
    result = await db.exec(
        select(CarbonReport.year).distinct().order_by(desc(CarbonReport.year))
    )
    years = [str(y) for y in result.all()]
    if not years:
        return {"years": [], "latest": ""}
    return {"years": years, "latest": years[0]}


@router.get("/report/usage")
async def report_usage(
    filters: BackofficeFilters = Depends(get_backoffice_filters),
    format: str = Query("csv", description="Export format: csv or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "export")),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail=ERROR_INVALID_FORMAT)

    try:
        data = await CarbonReportModuleRepository(db).get_usage_report(
            path_affiliation=filters.path_affiliation,
            path_lvl4=filters.path_lvl4,
            completion_status=filters.completion_status,
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
    current_user: User = Depends(require_permission("backoffice.users", "export")),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail=ERROR_INVALID_FORMAT)

    timestamp = datetime.now(timezone.utc).strftime(EXPORT_CSV_TIMESTAMP_FORMAT)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for module_type, data_entry_types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
            for data_entry_type in data_entry_types:
                try:
                    data = await CarbonReportModuleRepository(db).get_detailed_report(
                        data_entry_type=data_entry_type,
                        path_affiliation=filters.path_affiliation,
                        path_lvl4=filters.path_lvl4,
                        completion_status=filters.completion_status,
                        search=filters.search,
                        modules=filters.modules,
                        years=filters.years,
                    )
                except ValueError as exc:
                    # Invalid filter values or other issues in query parameters
                    raise HTTPException(status_code=400, detail=str(exc))

                if data is None or len(data) == 0:
                    continue

                file_path = (
                    tmp_path / f"{module_type.name}_{data_entry_type.name}.{format}"
                )
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
    current_user: User = Depends(require_permission("backoffice.users", "export")),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail=ERROR_INVALID_FORMAT)

    try:
        data = await CarbonReportModuleRepository(db).get_results_report(
            path_affiliation=filters.path_affiliation,
            path_lvl4=filters.path_lvl4,
            completion_status=filters.completion_status,
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
