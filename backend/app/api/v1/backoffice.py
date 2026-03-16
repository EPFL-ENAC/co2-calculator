"""Backoffice API endpoints."""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.carbon_report import (
    CarbonReport,
    ModuleStatus,
)
from app.models.user import User
from app.repositories.carbon_report_module_repo import (
    CarbonReportModuleRepository,
)
from app.repositories.unit_repo import UnitRepository
from app.schemas.backoffice import (
    PaginatedUnitReportingData,
    PaginationMeta,
    UnitReportingData,
)

logger = get_logger(__name__)
router = APIRouter()


class CompletionCounts(BaseModel):
    validated: int
    in_progress: int
    default: int


class ModuleCompletion(BaseModel):
    status: str  # "validated", "in-progress", "default"
    outlier_values: int


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
        isinstance(key, str) and key.isdigit() and len(key) == 4
        for key in completion.keys()
    )


def _get_year_keys(completion: dict) -> list[str]:
    """Extract all year keys from completion data."""
    return [
        k
        for k in completion.keys()
        if isinstance(k, str) and k.isdigit() and len(k) == 4
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
    status_order = {"validated": 3, "in-progress": 2, "default": 1}

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
                if status_order.get(new_status, 0) > status_order.get(
                    current_status, 0
                ):
                    aggregated[module_name]["status"] = new_status
                current_outlier = aggregated[module_name].get("outlier_values", 0)
                if isinstance(current_outlier, int):
                    aggregated[module_name]["outlier_values"] = (
                        current_outlier + new_outlier
                    )

    return aggregated


def calculate_completion_counts(
    completion: dict, years: list[str] | None = None
) -> CompletionCounts:
    """
    Calculate counts for each completion status across all selected years.
    Returns total validated/in-progress/default module-year combinations.
    """
    if not _is_year_based(completion):
        # Old format - count by module
        counts = {"validated": 0, "in_progress": 0, "default": 0}
        for module_data in completion.values():
            status = get_module_status(module_data)
            if status == "validated":
                counts["validated"] += 1
            elif status == "in-progress":
                counts["in_progress"] += 1
            else:
                counts["default"] += 1
        return CompletionCounts(**counts)

    years_to_check = _get_years_to_process(completion, years)
    counts = {"validated": 0, "in_progress": 0, "default": 0}

    for year_str in years_to_check:
        year_data = completion.get(year_str, {})
        if not isinstance(year_data, dict):
            continue

        for module_data in year_data.values():
            status = get_module_status(module_data)
            if status == "validated":
                counts["validated"] += 1
            elif status == "in-progress":
                counts["in_progress"] += 1
            else:
                counts["default"] += 1

    return CompletionCounts(**counts)


def calculate_total_outlier_values(
    completion: dict, years: list[str] | None = None
) -> int:
    """
    Calculate total outlier values by summing all module outlier_values,
    optionally filtered by years.
    """
    completion_data = get_completion_for_years(completion, years)
    total = 0
    for module_data in completion_data.values():
        total += get_module_outlier_values(module_data)
    return total


def _is_unit_complete(completion: dict, years: list[str] | None = None) -> bool:
    """
    Check if a unit is complete: all modules must be validated in ALL selected years.
    If no years selected, checks all years.
    Total required: 7 modules × number of years
    """
    if not _is_year_based(completion):
        return len(completion) == 7 and all(
            get_module_status(module_data) == "validated"
            for module_data in completion.values()
        )

    years_to_check = _get_years_to_process(completion, years)
    expected_total = 7 * len(years_to_check)
    validated_count = sum(
        1
        for year in years_to_check
        for module_data in completion.get(year, {}).values()
        if get_module_status(module_data) == "validated"
    )

    return validated_count == expected_total


@router.get("/units", response_model=PaginatedUnitReportingData)
async def list_backoffice_units(
    path_lvl2: Optional[List[str]] = Query(
        None, description="Filter by VP and Faculties"
    ),
    path_lvl3: Optional[List[str]] = Query(None, description="Filter by Institutes"),
    path_lvl4: Optional[List[str]] = Query(
        None, description="Filter by unit name(s) - can specify multiple"
    ),
    completion_status: Optional[ModuleStatus] = Query(
        None,
        description="Filter by completion status ModuleStatus",
    ),
    search: Optional[str] = Query(
        None, description="Search in unit name, path, or principal user"
    ),
    modules: Optional[List[str]] = Query(
        None,
        description="""Filter by module states, format: 'module_name:state'
        (e.g., 'headcount:validated')""",
    ),
    years: Optional[List[int]] = Query(
        None, description="Filter by years (e.g., [2024, 2025])"
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page"),
    current_user: User = Depends(require_permission("backoffice.users", "view")),
    db: AsyncSession = Depends(get_db),
):
    """
    List units with their reporting completion status and outlier values,
    """
    carbon_report_repo = CarbonReportModuleRepository(db)
    if years is None or len(years) == 0:
        raise ValueError("At least one year must be specified for reporting overview")
    result = await carbon_report_repo.get_reporting_overview(
        path_lvl2=path_lvl2,
        path_lvl3=path_lvl3,
        path_lvl4=path_lvl4,
        completion_status=completion_status,
        search=search,
        modules=modules,
        years=years,  # Default to first year for overview for now
        page=page,
        page_size=page_size,
    )
    # data, total, page, page_size, total_pages = result

    # return result.get("data", [])

    # Convert the data to UnitReportingData instances
    unit_reporting_data = []
    for item in result.get("data", []):
        if isinstance(item, dict):
            unit_reporting_data.append(UnitReportingData(**item))
        else:
            unit_reporting_data.append(item)

    return PaginatedUnitReportingData(
        data=unit_reporting_data,
        pagination=PaginationMeta(**result),
    )


@router.get("/export")
async def export_reporting(
    path_lvl2: Optional[List[str]] = Query(
        None, description="Filter by VP and Faculties"
    ),
    path_lvl3: Optional[List[str]] = Query(None, description="Filter by Institutes"),
    path_lvl4: Optional[List[str]] = Query(
        None, description="Filter by unit name(s) - can specify multiple"
    ),
    completion_status: Optional[ModuleStatus] = Query(
        None, description="Filter by completion status (complete, incomplete)"
    ),
    search: Optional[str] = Query(
        None, description="Search in unit name, affiliation, or principal user"
    ),
    modules: Optional[List[str]] = Query(
        None,
        description="""Filter by module states, format: 'module_name:state'
        (e.g., 'headcount:validated')""",
    ),
    years: Optional[List[int]] = Query(
        None, description="Filter by years (e.g., [2024, 2025])"
    ),
    format: str = Query("csv", description="Export format: csv or json"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    # TODO: for export, we might want to allow larger page sizes
    # or even no pagination to get all data at once
    # it was 10000, not sure how to handle millions of rows if that ever happens
    # - maybe we should stream the data instead of loading it all in memory?
    page_size: int = Query(100, ge=1, le=100, description="Number of items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "export")),
):
    """Export unit reporting data as CSV or JSON file download."""
    # Get all matching records for export
    reporting_data = await list_backoffice_units(
        path_lvl2=path_lvl2,
        path_lvl3=path_lvl3,
        path_lvl4=path_lvl4,
        completion_status=completion_status,
        search=search,
        modules=modules,
        years=years,
        page=page,
        page_size=page_size,
        current_user=current_user,
        db=db,
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if format == "json":
        # JSON export
        export_data = [doc.model_dump() for doc in reporting_data.data]

        content = json.dumps(export_data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="reporting_export_{today}.json"'
                ),
            },
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "unit_name",
                "affiliation",
                "validation_status",
                "principal_user",
                "last_update",
                "highest_result_category",
                "total_carbon_footprint",
                "view_url",
            ]
        )

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
                    f'attachment; filename="reporting_export_{today}.csv"'
                ),
            },
        )


@router.get("/unit/{unit_id}", response_model=UnitReportingData)
async def get_backoffice_unit(
    unit_id: int,
    years: Optional[List[str]] = Query(
        None, description="Filter by years (e.g., ['2024', '2025'])"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "view")),
):
    """
    Get detailed reporting data for a specific unit.

    Returns unit information with carbon footprint data for specified years.
    """
    unit_repo = UnitRepository(db)

    # Get unit details
    unit_result = await unit_repo.get_by_id(unit_id)
    if not unit_result:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Unit not found")

    # Get reporting data for the unit
    # Simplified version - in production, query actual carbon report data
    unit_reporting_data = UnitReportingData(
        id=unit_id,
        unit_name=unit_result.name if hasattr(unit_result, "name") else "Unknown",
        affiliation=unit_result.affiliation
        if hasattr(unit_result, "affiliation")
        else "Unknown",
        validation_status="N/A",
        principal_user=(
            unit_result.principal_user_institutional_id
            if hasattr(unit_result, "principal_user_institutional_id")
            and unit_result.principal_user_institutional_id
            else "Unknown"
        ),
        last_update=None,
        highest_result_category=None,
        total_carbon_footprint=0.0,
        view_url=f"/units/{unit_id}/reporting",
        completion=None,
    )

    return unit_reporting_data


@router.get("/years")
async def get_available_years(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "view")),
):
    """
    Get all available years from all units combined.
    Returns all unique years found across all units' carbon reports,
    sorted in descending order (latest first).
    """

    # Query distinct years from carbon reports
    from sqlmodel import col

    stmt = (
        select(CarbonReport.year).where(col(CarbonReport.year).isnot(None)).distinct()
    )
    result = await db.exec(stmt)
    years = [str(year) for year in result.all() if year]

    # Sort years in descending order (latest first)
    sorted_years = sorted(
        years, key=lambda y: int(y) if y.isdigit() else 0, reverse=True
    )

    latest_year = sorted_years[0] if sorted_years else None

    return {"years": sorted_years, "latest": latest_year}
