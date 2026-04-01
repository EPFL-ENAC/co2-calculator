"""Backoffice API endpoints."""

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.carbon_report import (
    CarbonReport,
    CarbonReportModule,
    CarbonReportModuleRead,
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
from app.schemas.unit import UnitRead

# Services
from app.services.data_entry_service import DataEntryService

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
        (e.g., 'headcount:validated') --> not implemented yet, use enum""",
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
    carbon_report_module_repo = CarbonReportModuleRepository(db)
    # carbon_report_repo = CarbonReportRepository(db)
    if years is None or len(years) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one year must be specified for reporting overview",
        )
    # data = await carbon_report_repo.get_reporting_overview(
    #    path_lvl2=path_lvl2,
    #    path_lvl3=path_lvl3,
    #    path_lvl4=path_lvl4,
    #    completion_status=completion_status,
    #    search=search,
    #    modules=modules,
    #    years=years,
    #    page=page,
    #    page_size=page_size,
    # )
    result = await carbon_report_module_repo.get_reporting_overview(
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
                    unit_name=item.get("unit_name", "Unknown Unit"),
                    affiliation=item.get("affiliation", "Unknown Affiliation"),
                    validation_status=item.get("validation_status", "unknown"),
                    principal_user=item.get("principal_user", "Unknown User"),
                    last_update=item.get("last_update"),
                    highest_result_category=item.get("highest_result_category"),
                    total_carbon_footprint=item.get("total_carbon_footprint", 0.0),
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


# usage !?
# SELECT
#     cr.id AS report_id,
#     cr.year,
#     cr.unit_id,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 1) AS headcount_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 2) AS
#   professional_travel_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 3) AS buildings_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 4) AS
#   equipment_electric_consumption_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 5) AS purchase_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 6) AS
#   research_facilities_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 7) AS
#   external_cloud_and_ai_status,
#     MAX(crm.status) FILTER (WHERE crm.module_type_id = 8) AS process_emissions_status,
#     cr.last_updated,
#     cr.completion_progress,
#     cr.overall_status
# FROM carbon_reports cr
# LEFT JOIN carbon_report_modules crm
#     ON crm.carbon_report_id = cr.id
# GROUP BY cr.id, cr.year, cr.unit_id, cr.last_updated, cr.completion_progress,
#   cr.overall_status
# ORDER BY cr.id;

# or different usage
# SELECT
#     cr.id AS report_id,
#     cr.year,
#     cr.unit_id,
#     CASE crm.module_type_id
#         WHEN 1 THEN 'headcount'
#         WHEN 2 THEN 'professional_travel'
#         WHEN 3 THEN 'buildings'
#         WHEN 4 THEN 'equipment_electric_consumption'
#         WHEN 5 THEN 'purchase'
#         WHEN 6 THEN 'research_facilities'
#         WHEN 7 THEN 'external_cloud_and_ai'
#         WHEN 8 THEN 'process_emissions'
#     END AS module_name,
#     crm.status AS module_status,
#     cr.last_updated,
#     cr.stats,
#     cr.completion_progress,
#     cr.overall_status
# FROM carbon_reports cr
# JOIN carbon_report_modules crm
#     ON crm.carbon_report_id = cr.id
# ORDER BY cr.id, crm.module_type_id;


@router.get("/export-detailed")
async def export_detailed_reporting(
    path_name: Optional[str] = Query(
        None, description="Filter by path name(s) - can specify multiple"
    ),
    units: Optional[List[str]] = Query(
        None, description="Filter by unit name(s) - can specify multiple"
    ),
    years: Optional[List[str]] = Query(
        None, description="Filter by years (e.g., ['2024', '2025'])"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "export")),
):
    """
        Export detailed reporting data for all units, including module-level details.
        Creates one CSV per unit/year/module combination using response
          DTOs and packages them in a ZIP file.
        File naming format: {AFFILIATION}_{UNIT_NAME}_{YEAR}_module_{MODULE_TYPE}.csv

        We can do it faster if we skip the DTO validation and just dump the
        raw data from the database,
        like so

    SELECT
        cr.year,
        de.data_entry_type_id,
        u.institutional_id,
        de.id,

        j.name,
        j.equipment_class,
        j.sub_class,

        SUM(dee.kg_co2eq) AS total_kg_co2eq

    FROM data_entries de

    JOIN carbon_report_modules crm ON crm.id = de.carbon_report_module_id
    JOIN carbon_reports cr ON cr.id = crm.carbon_report_id
    JOIN units u ON u.id = cr.unit_id

    LEFT JOIN data_entry_emissions dee ON dee.data_entry_id = de.id

    -- JSON → columns
    LEFT JOIN LATERAL jsonb_to_record(de.data::jsonb) AS j(

            name TEXT,
            equipment_class TEXT,
            sub_class TEXT,
            active_usage_hours_per_week INT,
            standby_usage_hours_per_week INT,
            note TEXT
    ) ON TRUE

    WHERE de.data_entry_type_id = 10

    GROUP BY
        cr.year,
        de.data_entry_type_id,
        u.institutional_id,
        de.id,
        j.name,
        j.equipment_class,
        j.sub_class;



    """
    # Get units based on filters
    unit_repo = UnitRepository(db)
    units_result = await unit_repo.get_units_with_filters(
        years=[int(y) for y in years] if years else None,
        path_name=path_name,
        name=units[0] if units and len(units) == 1 else None,
        page=1,
        page_size=10,
    )
    filtered_units: List[UnitRead] = units_result["data"]

    # If no units found, return empty ZIP
    if not filtered_units:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("README.txt", "No data found for the specified filters.")
        zip_buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; "
                f'filename="detailed_export_{timestamp}.zip"'
            },
        )

    # Get years to process
    year_list = [int(y) for y in years] if years else [2024, 2025, 2026]

    # Initialize data entry service
    data_entry_service = DataEntryService(db)

    # Collect CSV data for each unit/year/module combination
    csv_files_data = []

    # Process each unit and year
    for unit in filtered_units:
        # Create unit path for file naming (e.g., "STI_LMSC")
        unit_path = "UNKNOWN_PATH"
        if unit.path_name:
            unit_path = f"{unit.path_name.replace(' ', '_')}"

        for year in year_list:
            # Get carbon report for this unit and year
            report_stmt = select(CarbonReport).where(
                CarbonReport.unit_id == unit.id, CarbonReport.year == year
            )
            report_result = await db.exec(report_stmt)
            carbon_report = report_result.one_or_none()

            if not carbon_report:
                continue

            # Get all modules for this report
            modules_stmt = select(CarbonReportModule).where(
                CarbonReportModule.carbon_report_id == carbon_report.id
            )
            modules_result = await db.exec(modules_stmt)
            db_modules = modules_result.all()
            modules = [CarbonReportModuleRead.model_validate(m) for m in db_modules]
            # Process each module
            for module in modules:
                try:
                    # Get submodule data using the proper service method
                    # We need to determine the data entry type IDs for this module
                    # For now, let's get all data entry types for this module
                    module_data = await data_entry_service.get_module_data(
                        carbon_report_module_id=module.id,
                    )

                    # Get data for each submodule type within this module
                    for (
                        data_entry_type_id,
                        count,
                    ) in module_data.data_entry_types_total_items.items():
                        if count > 0:  # Only process submodules that have data
                            # Get the submodule data with proper response DTOs
                            submodule_data = (
                                await data_entry_service.get_submodule_data(
                                    carbon_report_module_id=module.id,
                                    data_entry_type_id=data_entry_type_id,
                                    limit=10000,  # Get all items
                                    offset=0,
                                    sort_by="id",
                                    sort_order="asc",
                                )
                            )

                            if submodule_data.items:
                                # Create CSV content for this
                                # unit/year/module/submodule combination
                                csv_buffer = io.StringIO()
                                writer = csv.writer(csv_buffer)

                                # Write header based on first entry
                                first_entry_dict = submodule_data.items[0].model_dump()
                                writer.writerow(first_entry_dict.keys())

                                # Write data rows
                                for entry in submodule_data.items:
                                    entry_dict = entry.model_dump()

                                    writer.writerow(entry_dict.values())

                                # Add CSV to our collection with proper naming
                                # Map data entry type to module type name
                                module_type_name = _get_module_type_name(
                                    data_entry_type_id
                                )
                                filename = (
                                    f"{unit_path}_{year}_module_{module_type_name}.csv"
                                )
                                csv_files_data.append(
                                    {
                                        "filename": filename,
                                        "content": csv_buffer.getvalue(),
                                    }
                                )

                except Exception as e:
                    logger.warning(
                        f"Failed to process module {module.id} "
                        f"for unit {unit.id} year {year}: {e}"
                    )
                    continue

    # Create ZIP file with all CSVs
    zip_buffer = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add each CSV file to the ZIP
        for csv_data in csv_files_data:
            if csv_data["content"]:
                zip_file.writestr(csv_data["filename"], csv_data["content"])

    zip_buffer.seek(0)

    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; "
            f'filename="detailed_export_{timestamp}.zip"'
        },
    )


def _get_module_type_name(data_entry_type_id: int) -> str:
    """Convert data entry type ID to module type name for file naming."""
    type_mapping = {
        1: "headcount_member",
        2: "headcount_student",
        9: "equipment_scientific",
        10: "equipment_it",
        11: "equipment_other",
        20: "professional_travel",
        40: "external_cloud",
        41: "external_ai",
        50: "process_emissions",
    }
    return type_mapping.get(data_entry_type_id, f"unknown_{data_entry_type_id}")


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
    current_user: User = Depends(require_permission("backoffice.users", "view")),
):
    return {"message": f"Details for unit {unit_id} with year filter {years}"}


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
    path_lvl2: Optional[List[str]] = Query(
        None, description="Filter by VP and Faculties"
    ),
    path_lvl3: Optional[List[str]] = Query(None, description="Filter by Institutes"),
    path_lvl4: Optional[List[str]] = Query(
        None, description="Filter by unit name(s) - can specify multiple"
    ),
    completion_status: Optional[ModuleStatus] = Query(
        None,
        description=(
            "Filter by completion status: NOT_STARTED (0), IN_PROGRESS (1), "
            "VALIDATED (2)"
        ),
    ),
    search: Optional[str] = Query(
        None, description="Search in unit name, affiliation, or principal user"
    ),
    modules: Optional[List[str]] = Query(
        None,
        description="""Filter by module states, format: 'module_name:state'
        (e.g., 'headcount:0' for default, 'headcount:1' for in-progress, 
        'headcount:2' for validated)""",
    ),
    years: Optional[List[int]] = Query(
        None, description="Filter by years (e.g., [2024, 2025])"
    ),
    format: str = Query("csv", description="Export format: csv or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("backoffice.users", "export")),
) -> StreamingResponse:
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail="Invalid format specified")

    try:
        data = await CarbonReportModuleRepository(db).get_usage_report(
            path_lvl2=path_lvl2,
            path_lvl3=path_lvl3,
            path_lvl4=path_lvl4,
            completion_status=completion_status,
            search=search,
            modules=modules,
            years=years,
        )
    except ValueError as exc:
        # Invalid filter values or other issues in query parameters
        raise HTTPException(status_code=400, detail=str(exc))

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if format == "json":
        content = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="usage_report_{today}.json"'
                ),
            },
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        if data:
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow(row.values())
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="usage_report_{today}.csv"'
                ),
            },
        )
