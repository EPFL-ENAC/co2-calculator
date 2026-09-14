"""Carbon Report API endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.policy import (
    require_explore_ownership,
    require_module_unit_scope,
    require_plan_scope_for_report,
    require_unit_access,
)
from app.db import SessionLocal
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport
from app.models.unit import Unit
from app.models.user import User
from app.schemas.carbon_report import (
    CarbonReportBudgetUpdate,
    CarbonReportCreate,
    CarbonReportModuleActiveUpdate,
    CarbonReportModuleRead,
    CarbonReportModuleUpdate,
    CarbonReportRead,
    CarbonReportReferencePercentageUpdate,
    CarbonReportSubmoduleBudgetUpdate,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.utils.factor_year import resolve_factor_year_safe
from app.workflows.explore_provisioning import ExploreProvisioningWorkflow


async def _carbon_report_read(
    db: AsyncSession, report: CarbonReport | CarbonReportRead
) -> CarbonReportRead:
    """Build a response carrying the report's resolved factor year (#2631).

    Not Explore-specific despite where it was first added: any route
    returning a single ``CarbonReportRead`` should carry a consistent
    ``factor_year`` — the dedicated Explore GET already did, but the
    generic by-id GET (also reachable for an Explore report, #2461's
    ownership gate) silently left it ``None``, which read as a bug to
    anyone comparing the two responses for the same report.
    """
    factor_year = await resolve_factor_year_safe(db, report)
    return CarbonReportRead.model_validate(report).model_copy(
        update={"factor_year": factor_year}
    )


async def _cleanup_old_explore_background(
    unit_id: int, created_by: int, keep_project_id: int
) -> None:
    """Delete the user's other Simulator Explore sandboxes for a unit (#2656).

    Runs as a FastAPI background task right after a fresh sandbox is
    created and the response has been sent. Opens its own session so the
    request session lifetime is not a concern. Replaces the old TTL-refresh
    task: creation and cleanup are now two separate, explicit steps.

    Caught and logged, not re-raised: the response is already sent, so a
    failure here can only be surfaced through logs. Mirrors the same
    catch-log-move-on shape as the other background tasks in this codebase
    (``app/tasks/audit_sync_tasks.py``) — a failed cleanup leaves stale
    sandboxes behind rather than crashing anything, and the next
    "start exploration" call sweeps them along with the one from this run.
    """
    try:
        async with SessionLocal() as db:
            service = CarbonReportService(db)
            await service.delete_old_explore(
                unit_id=unit_id, created_by=created_by, keep_project_id=keep_project_id
            )
            await db.commit()
    except Exception as exc:
        logger.error(
            f"Explore sandbox cleanup failed for unit_id={unit_id} "
            f"created_by={created_by} keep_project_id={keep_project_id}: {exc}",
            exc_info=True,
        )


logger = get_logger(__name__)
router = APIRouter()


@router.get("/unit/{unit_id}/", response_model=list[CarbonReportRead])
async def list_carbon_reports_by_unit(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all carbon reports for a given unit."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    return await service.list_by_unit(unit_id)


@router.get("/unit/{unit_id}/year/{year}/", response_model=CarbonReportRead)
async def get_carbon_report_by_unit_and_year(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return 404 if not found, else retrieve carbon report for unit and year."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    report = await service.get_by_unit_and_year(unit_id, year)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    return report


@router.post("/", response_model=CarbonReportRead, status_code=status.HTTP_201_CREATED)
async def create_carbon_report(
    report: CarbonReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new carbon report for a given unit and year."""
    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    service = CarbonReportService(db)
    result = await service.create(report)
    await db.commit()
    return result


@router.get(
    "/simulator/explore/unit/{unit_id}/",
    response_model=CarbonReportRead,
)
async def get_simulator_explore_carbon_report(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the user's current Simulator Explore sandbox for a unit.

    Read-only: no create-fallback (404 if none exists yet), no staleness
    handling — #2656 removed the year key and the TTL refresh entirely. A
    sandbox exists only once a POST creates it, and is replaced, not
    refreshed, by the next POST.
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID missing",
        )
    service = CarbonReportService(db)
    result = await service.get_explore(unit_id=unit_id, created_by=current_user.id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="Simulator Explore report not found"
        )
    return await _carbon_report_read(db, result)


@router.post(
    "/simulator/explore/unit/{unit_id}/",
    response_model=CarbonReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulator_explore_carbon_report(
    unit_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new Simulator Explore sandbox (#2656).

    Always creates — no idempotency, no existence check. "Start an
    exploration" (a page mount or a refresh alike) always gets a brand-new
    empty sandbox; the caller's other sandboxes for this unit are deleted in
    the background right after. Replaces the old idempotent PUT (#2487) and
    the 24h TTL refresh it triggered.
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID missing",
        )
    result = await ExploreProvisioningWorkflow(db).create(
        unit_id=unit_id, created_by=current_user.id
    )
    if result.carbon_project_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Explore sandbox created without a project id",
        )
    background_tasks.add_task(
        _cleanup_old_explore_background,
        unit_id=unit_id,
        created_by=current_user.id,
        keep_project_id=result.carbon_project_id,
    )
    return await _carbon_report_read(db, result)


@router.get("/{carbon_report_id}", response_model=CarbonReportRead)
async def get_carbon_report(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a carbon report by ID."""
    service = CarbonReportService(db)
    report = await service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    if report.carbon_project_id is not None:
        project = await db.get(CarbonProject, report.carbon_project_id)
        require_explore_ownership(current_user, project)
    return await _carbon_report_read(db, report)


# --- CarbonReportModule endpoints ---


@router.get("/{carbon_report_id}/modules/", response_model=list[CarbonReportModuleRead])
async def list_carbon_report_modules(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all modules for a carbon report with their statuses.

    Plan 310-D / Issue #1062 — pipeline state lives in the unified
    frontend ``pipelineStateStore`` driven by
    ``GET /v1/sync/active-pipelines``.  This endpoint returns the
    pure module-status read.
    """
    # First verify carbon report exists
    report_service = CarbonReportService(db)
    report = await report_service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")

    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)

    module_service = CarbonReportModuleService(db)
    return await module_service.list_modules(carbon_report_id)


@router.patch(
    "/{carbon_report_id}/modules/{module_type_id}/status",
    response_model=CarbonReportModuleRead,
)
async def update_carbon_report_module_status(
    carbon_report_id: int,
    module_type_id: int,
    update: CarbonReportModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the status of a carbon report module.

    Status values:
    - 0: not_started
    - 1: in_progress
    - 2: validated
    """
    # First verify carbon report exists
    report_service = CarbonReportService(db)
    report = await report_service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")

    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    # Validating a module's status is a unit-level action: principal/global
    # only. A standard user (own breadth) is rejected here even though they may
    # edit their own records.
    require_module_unit_scope(
        current_user,
        module_type_id,
        (unit.institutional_id or "") if unit else "",
    )

    module_service = CarbonReportModuleService(db)
    try:
        result = await module_service.update_status(
            carbon_report_id, module_type_id, update.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                f"""Module type {module_type_id} not found for
                carbon report {carbon_report_id}"""
            ),
        )

    await report_service.recompute_report_stats(carbon_report_id)
    await report_service.recompute_report_progress(carbon_report_id)
    await db.commit()
    return result


@router.patch(
    "/{carbon_report_id}/modules/{module_type_id}/active",
    response_model=CarbonReportModuleRead,
)
async def update_carbon_report_module_active(
    carbon_report_id: int,
    module_type_id: int,
    update: CarbonReportModuleActiveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a module's Active flag (Simulator Plan checkbox).

    Inactive modules are excluded from the report's sums, stats and
    completion progress; the report stats are recomputed immediately.
    """
    report_service = CarbonReportService(db)
    report = await report_service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")

    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    await require_plan_scope_for_report(db, current_user, report, "edit")

    module_service = CarbonReportModuleService(db)
    result = await module_service.update_is_active(
        carbon_report_id, module_type_id, update.is_active
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Module type {module_type_id} not found for "
                f"carbon report {carbon_report_id}"
            ),
        )

    await report_service.recompute_report_stats(carbon_report_id)
    await report_service.recompute_report_progress(carbon_report_id)
    await db.commit()
    return result


async def _require_grant_report_edit(
    db: AsyncSession, current_user: User, carbon_report_id: int
) -> CarbonReportService:
    """Load a Project Grant report and enforce plan-edit access on it.

    404 when the report is missing, 409 when it is not a grant report —
    budgets exist only on the Project Grant section (#1978).
    """
    report_service = CarbonReportService(db)
    report = await report_service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    unit = await db.get(Unit, report.unit_id)
    require_unit_access(current_user, unit)
    await require_plan_scope_for_report(db, current_user, report, "edit")
    if not report.is_grant:
        raise HTTPException(
            status_code=409,
            detail="Budgets only apply to Project Grant reports",
        )
    return report_service


@router.patch("/{carbon_report_id}/budget", response_model=CarbonReportRead)
async def update_carbon_report_budget(
    carbon_report_id: int,
    update: CarbonReportBudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a Project Grant report's total budget (#1978)."""
    report_service = await _require_grant_report_edit(
        db, current_user, carbon_report_id
    )
    result = await report_service.set_budget(
        carbon_report_id, update.budget, update.budget_currency
    )
    if not result:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    await db.commit()
    return result


@router.patch(
    "/{carbon_report_id}/modules/{module_type_id}/reference-percentage",
    response_model=dict,
)
async def update_carbon_report_module_reference_percentage(
    carbon_report_id: int,
    module_type_id: int,
    update: CarbonReportReferencePercentageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Apply one reference percentage to every snapshot entry of a module.

    Backs the grant equipment "global percentage" mode (#1981): the
    calculator's prefilled lines are kept and one percentage prices them
    all. Only Project Grant reports carry this mode.
    """
    report_service = await _require_grant_report_edit(
        db, current_user, carbon_report_id
    )
    module_service = CarbonReportModuleService(db)
    updated = await module_service.set_reference_percentage_all(
        carbon_report_id, module_type_id, update.percentage
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Module type {module_type_id} not found for "
                f"carbon report {carbon_report_id}"
            ),
        )
    await report_service.recompute_report_stats(carbon_report_id)
    await db.commit()
    return {"updated_entries": updated}


@router.patch(
    "/{carbon_report_id}/modules/{module_type_id}/budget",
    response_model=CarbonReportModuleRead,
)
async def update_carbon_report_submodule_budget(
    carbon_report_id: int,
    module_type_id: int,
    update: CarbonReportSubmoduleBudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a grant submodule's share of the budget (#1978).

    The frontend checks the submodule budgets against the grant's total and
    surfaces the non-distributed or over-distributed remainder.
    """
    await _require_grant_report_edit(db, current_user, carbon_report_id)
    module_service = CarbonReportModuleService(db)
    result = await module_service.update_submodule_budget(
        carbon_report_id, module_type_id, update.submodule, update.budget
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Module type {module_type_id} not found for "
                f"carbon report {carbon_report_id}"
            ),
        )
    await db.commit()
    return result
