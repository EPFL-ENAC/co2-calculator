"""Module stats API endpoints.

The heavy chart payloads (emission breakdown, IT breakdown) are gone: the
frontend reads the persisted ``carbon_report.stats`` /
``carbon_report_module.stats`` shapes written at recompute time. Only the
results summary remains an endpoint because it compares against the
previous year's report, which can change after this report was computed.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.constants import ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportModule, CarbonReportType
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import User
from app.repositories.carbon_report_repo import CarbonReportRepository
from app.schemas.carbon_report import CarbonReportModuleRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.services.data_entry_service import DataEntryService
from app.services.unit_service import UnitService
from app.services.unit_totals_service import UnitTotalsService
from app.utils.report_computations import (
    compute_results_summary,
    compute_validated_totals,
)
from app.utils.report_stats import (
    derive_quantity_sections,
    merge_report_stats,
)

logger = get_logger(__name__)
router = APIRouter()


async def build_validated_totals(db: AsyncSession, carbon_report_id: int) -> dict:
    """Compute validated totals for a carbon report from persisted stats.

    Aggregates emissions (kg → tonnes CO2eq) and FTE across all validated
    modules. Both are keyed by module_type_id so headcount appears with
    total_fte while other modules show total_tonnes_co2eq. Simulator Explore
    reports have no validation step, so every module counts there.

    Returns:
        {
            "modules": {1: 25.5, 2: 15.0, 4: 41.7, 7: 5.0},
            "total_tonnes_co2eq": 61.7,
            "total_fte": 25.5
        }
    """
    report_type_row = await db.execute(
        select(CarbonProject.carbon_report_type)
        .join(
            CarbonReport, col(CarbonReport.carbon_project_id) == col(CarbonProject.id)
        )
        .where(col(CarbonReport.id) == carbon_report_id)
    )
    report_type = report_type_row.scalar_one_or_none()
    validated_only = report_type != CarbonReportType.SIMULATOR_EXPLORE

    rows = (
        await db.execute(
            select(
                col(CarbonReportModule.module_type_id),
                col(CarbonReportModule.status),
                col(CarbonReportModule.stats),
            ).where(col(CarbonReportModule.carbon_report_id) == carbon_report_id)
        )
    ).all()

    emission_stats: dict[str, float] = {}
    fte_stats: dict[str, float] = {}
    for module_type_id, module_status, stats in rows:
        if validated_only and module_status != ModuleStatus.VALIDATED:
            continue
        if not isinstance(stats, dict):
            continue
        total = stats.get("total", 0.0) or 0.0
        if total:
            emission_stats[str(module_type_id)] = total
        if stats.get("total_fte"):
            fte_stats[str(module_type_id)] = stats["total_fte"]

    return compute_validated_totals(
        emission_stats, fte_stats, str(ModuleTypeEnum.headcount.value)
    )


@router.get(
    "/{unit_id}/{year}/{module_id}/stats", response_model=dict[str, float | None]
)
async def get_module_stats(
    unit_id: int,
    year: int,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, float | None]:
    """Get module statistics such as total items and submodules.

    Args:
        module_id: Module identifier
        unit_id: Unit ID to filter equipment
        year: Year for the data
        db: Database session
        current_user: Authenticated user
    Returns:
        Dict with statistics (e.g., total items, total kg_co2eq)
    """
    unit = await db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit {unit_id} not found",
        )
    await _check_module_permission(
        current_user,
        module_id,
        "view",
        institutional_id=unit.institutional_id,
    )

    logger.info(
        f"GET module stats: module_id={sanitize(module_id)}, "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}"
    )

    stats: dict[str, float | None] = {}
    carbon_report_module: CarbonReportModuleRead = await CarbonReportModuleService(
        db
    ).get_carbon_report_by_year_and_unit(
        unit_id=unit_id, year=year, module_type_id=ModuleTypeEnum[module_id]
    )

    if module_id == "equipment":
        stats = await DataEntryService(db).get_stats(
            carbon_report_module_id=carbon_report_module.id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module {module_id} not found",
        )
    logger.info(f"Module stats returned: {stats}")

    return stats


async def _authorize_unit_ids(
    db: AsyncSession,
    current_user: User,
    unit_ids: list[int],
) -> list[int]:
    """Validate requested units against the caller's allow-list, deduped.

    Every unit must be one the caller may see, per the same allow-list the
    workspace switcher is built from. A unit outside it yields 404 rather than
    403: the frontend turns any 403 into a hard redirect to /unauthorized, so a
    forged id must look like "not found", not trip that redirect.
    """
    if not unit_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one unit_id is required",
        )

    allowed_unit_ids = {
        unit["id"] for unit in await UnitService(db).get_user_units(current_user)
    }
    unknown = [unit_id for unit_id in unit_ids if unit_id not in allowed_unit_ids]
    if unknown:
        logger.info(
            "Merged stats requested for inaccessible units",
            extra={"unit_ids": sanitize(unknown), "user_id": sanitize(current_user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit(s) not found: {', '.join(str(u) for u in unknown)}",
        )

    return list(dict.fromkeys(unit_ids))


async def _authorize_and_resolve_reports(
    db: AsyncSession,
    current_user: User,
    unit_ids: list[int],
    year: int,
) -> list[CarbonReport]:
    """Resolve the CALCULATOR reports of the requested units, for one year.

    Units with no report for ``year`` are skipped, so the aggregate simply
    covers the units that do have one.
    """
    authorized_unit_ids = await _authorize_unit_ids(db, current_user, unit_ids)
    return await CarbonReportRepository(db).list_by_units(authorized_unit_ids, year)


@router.get("/merged/multi-year-report-stats", response_model=dict)
async def get_merged_multi_year_breakdown(
    unit_ids: list[int] = Query(default_factory=list),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return per-year emission breakdown summed over the requested units.

    Feeds the "Compare Years" pop-up: one entry per year with stat-bucket
    totals (``modules``) and scope totals (``scopes``) in tonnes CO2eq,
    aggregated in SQL from each report's persisted stats. Units with no
    reports simply contribute nothing; no report at all yields ``{"years": []}``.
    """
    logger.info(f"GET merged multi-year breakdown: unit_ids={sanitize(unit_ids)}")
    authorized_unit_ids = await _authorize_unit_ids(db, current_user, unit_ids)
    return {"years": await CarbonReportService(db).compare_years(authorized_unit_ids)}


@router.get("/merged/report-stats", response_model=dict)
async def get_merged_report_stats(
    unit_ids: list[int] = Query(default_factory=list),
    year: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Sum several units' persisted report stats into one payload.

    Same shape as ``/{carbon_report_id}/report-stats``, so the frontend derives
    its charts from it unchanged. ``merge_report_stats`` drops per-unit
    top-class detail on purpose, so the IT section's is re-ranked across all
    the reports here rather than unioned.
    """
    reports = await _authorize_and_resolve_reports(db, current_user, unit_ids, year)
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No carbon report found for year {year}",
        )

    merged = merge_report_stats([dict(report.stats or {}) for report in reports])

    report_ids = [report.id for report in reports if report.id is not None]
    merged["it"]["top_class_detail"] = await CarbonReportModuleService(
        db
    ).build_merged_it_top_classes(report_ids, report_year=year)

    validated_total = 0.0
    for report_id in report_ids:
        validated = await build_validated_totals(db, report_id)
        validated_total += validated["total_tonnes_co2eq"]
    merged["total_tonnes_validated_co2eq"] = validated_total

    return merged


@router.get("/merged/results-summary", response_model=dict)
async def get_merged_results_summary(
    unit_ids: list[int] = Query(default_factory=list),
    year: int = Query(...),
    exclude_modules: list[int] = Query(default_factory=list),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Results summary over several units, summed per module.

    Each unit contributes its own validated module totals and its own
    previous-year comparison basis, so the year-over-year figure stays
    meaningful for a combined perimeter.
    """
    reports = await _authorize_and_resolve_reports(db, current_user, unit_ids, year)
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No carbon report found for year {year}",
        )

    service = UnitTotalsService(db)
    current_emissions: dict[str, float] = {}
    current_fte: dict[str, float] = {}
    prev_emissions: dict[str, float] = {}
    for report in reports:
        if report.id is None:
            continue
        raw = await service.get_results_summary(report.id)
        for target, source in (
            (current_emissions, raw["current_emissions"]),
            (current_fte, raw["current_fte"]),
            (prev_emissions, raw["prev_emissions"]),
        ):
            for module_type_id, value in source.items():
                target[module_type_id] = target.get(module_type_id, 0.0) + (
                    value or 0.0
                )

    return compute_results_summary(
        current_emissions,
        current_fte,
        prev_emissions,
        get_settings().CO2_PER_KM_KG,
        str(ModuleTypeEnum.headcount.value),
        exclude_module_type_ids=set(exclude_modules),
    )


@router.get("/{carbon_report_id}/report-stats", response_model=dict)
async def get_report_stats(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the persisted report stats with the validated headline merged in.

    Same payload as the ``stats`` field of the workspace-home aggregate; used
    by the frontend to refresh charts after mutations without refetching the
    whole home bundle.
    """
    report = await db.get(CarbonReport, carbon_report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon report {carbon_report_id} not found",
        )
    stats = dict(report.stats or {})
    # Derived at read time so reports persisted before the section existed
    # still serve quantity donut data without waiting for a recompute.
    stats["quantities"] = derive_quantity_sections(stats.get("buckets") or {})
    validated = await build_validated_totals(db, carbon_report_id)
    stats["total_tonnes_validated_co2eq"] = validated["total_tonnes_co2eq"]
    return stats


@router.get("/{carbon_report_id}/validated-totals", response_model=dict)
async def get_validated_totals(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Validated-only totals per module (tonnes; FTE for headcount)."""
    return await build_validated_totals(db, carbon_report_id)


@router.get("/{carbon_report_id}/results-summary", response_model=dict)
async def get_results_summary(
    carbon_report_id: int,
    exclude_modules: list[int] = Query(default_factory=list),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get results summary for a carbon report, broken down by module.

    Returns unit-wide totals and per-module results including:
    - total_tonnes_co2eq, total_fte, tonnes_co2eq_per_fte
    - equivalent_car_km, previous year comparison
    """
    logger.info(f"GET results summary: carbon_report_id={sanitize(carbon_report_id)}")

    try:
        raw = await UnitTotalsService(db).get_results_summary(carbon_report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon report {carbon_report_id} not found",
        )

    return compute_results_summary(
        raw["current_emissions"],
        raw["current_fte"],
        raw["prev_emissions"],
        get_settings().CO2_PER_KM_KG,
        str(ModuleTypeEnum.headcount.value),
        exclude_module_type_ids=set(exclude_modules),
    )
