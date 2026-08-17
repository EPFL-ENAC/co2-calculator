"""Simulator plan (project planner) API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.policy import (
    plan_can_manage,
    plan_is_visible_to,
    require_plan_access,
    require_unit_access,
)
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.unit import Unit
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.simulator_plan import (
    SimulatorPlanCreate,
    SimulatorPlanPrefillStatus,
    SimulatorPlanRead,
    SimulatorPlanReferenceYearUpdate,
    SimulatorPlanUpdate,
    SimulatorPlanYearRead,
)
from app.services.simulator_plan_service import SimulatorPlanService
from app.tasks._background import fire_and_forget_or_defer_to_poller
from app.tasks.runner import run_job
from app.utils.report_stats import merge_report_stats

logger = get_logger(__name__)
router = APIRouter()


def _with_can_manage(
    current_user: User, plans: list[SimulatorPlanRead]
) -> list[SimulatorPlanRead]:
    """Stamp the caller's delete rights onto plan payloads for the frontend."""
    for plan in plans:
        plan.can_manage = plan_can_manage(current_user, plan)
    return plans


async def _require_plan_unit_access(
    db: AsyncSession, current_user: User, plan_id: int, action: str
) -> SimulatorPlanService:
    """Load the plan's unit and enforce access; 404 if the plan is missing.

    ``action``: "view" and "edit" both allow the creator, global roles, and
    unit members of a shared plan; "manage" (deletion) is creator/global only.
    """
    service = SimulatorPlanService(db)
    plan = await service.repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    unit = await db.get(Unit, plan.unit_id)
    require_unit_access(current_user, unit)
    require_plan_access(current_user, plan, action)
    return service


async def _enqueue_prefill(
    db: AsyncSession, current_user: User, plan_id: int, report_ids: list[int]
) -> int | None:
    """Queue the prefill of ``report_ids``; returns the job id, or None.

    Copying a reference year into a plan year is far too slow to run inside
    the request (plan #2050 Track F4) — the route persists the cheap
    metadata change and hands the copy to the job runner.

    ``module_type_id``/``data_entry_type_id`` stay NULL so Postgres'
    NULLS DISTINCT keeps the "one current per combo" partial unique index
    from firing: two plans prefilling at once must not collide.
    """
    if not report_ids:
        return None
    job = DataIngestionJob(
        job_type="simulator_plan_prefill",
        module_type_id=None,
        data_entry_type_id=None,
        year=None,
        ingestion_method=IngestionMethod.computed,
        target_type=TargetType.DATA_ENTRIES,
        entity_type=EntityType.GLOBAL_PER_YEAR,
        state=IngestionState.NOT_STARTED,
        provider=current_user.provider,
        meta={"config": {"plan_id": plan_id, "report_ids": report_ids}},
    )
    created = await DataIngestionRepository(db).create_ingestion_job(job)
    await db.commit()
    if created.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue plan prefill",
        )
    fire_and_forget_or_defer_to_poller(
        run_job(created.id), name=f"run_job-{created.id}"
    )
    return created.id


@router.get("/unit/{unit_id}/", response_model=list[SimulatorPlanRead])
async def list_simulator_plans(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the unit's simulator plans visible to the caller, newest first.

    Unshared plans of other unit members are omitted.
    """
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = SimulatorPlanService(db)
    plans = await service.list_plans(unit_id)
    return _with_can_manage(
        current_user, [p for p in plans if plan_is_visible_to(current_user, p)]
    )


@router.post(
    "/unit/{unit_id}/",
    response_model=SimulatorPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulator_plan(
    unit_id: int,
    plan: SimulatorPlanCreate | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a simulator plan; without a name, the next default is assigned."""
    unit = await db.get(Unit, unit_id)
    require_unit_access(current_user, unit)
    service = SimulatorPlanService(db)
    try:
        result = await service.create_plan(
            unit_id=unit_id,
            user=current_user,
            name=plan.name if plan else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return _with_can_manage(current_user, [result])[0]


@router.get("/{plan_id}", response_model=SimulatorPlanRead)
async def get_simulator_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a simulator plan by ID."""
    service = await _require_plan_unit_access(db, current_user, plan_id, "view")
    result = await service.get_plan(plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    require_plan_access(current_user, result, "view")
    return _with_can_manage(current_user, [result])[0]


@router.patch("/{plan_id}", response_model=SimulatorPlanRead)
async def update_simulator_plan(
    plan_id: int,
    plan: SimulatorPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a simulator plan (name, year range, lab visibility).

    Setting/changing the year range syncs the plan's per-year reports:
    missing years are created with their modules, out-of-range years are
    deleted together with their entries.
    """
    service = await _require_plan_unit_access(db, current_user, plan_id, "edit")
    try:
        updated = await service.update_plan(plan_id, plan)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    result, needs_prefill = updated
    await db.commit()
    result.prefill_job_id = await _enqueue_prefill(
        db, current_user, plan_id, needs_prefill
    )
    return _with_can_manage(current_user, [result])[0]


@router.get("/{plan_id}/prefill/{job_id}", response_model=SimulatorPlanPrefillStatus)
async def get_simulator_plan_prefill_status(
    plan_id: int,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll a deferred prefill job (plan #2050 Track F4).

    Gated by the plan's own access check rather than the admin data-sync
    permissions, since the caller here is the plan's editor waiting on
    their own PATCH.
    """
    await _require_plan_unit_access(db, current_user, plan_id, "view")
    job = await DataIngestionRepository(db).get_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Prefill job not found")
    config = (job.meta or {}).get("config") or {}
    if config.get("plan_id") != plan_id:
        # Don't let a plan's editor read another plan's job by id.
        raise HTTPException(status_code=404, detail="Prefill job not found")
    finished = job.state == IngestionState.FINISHED
    return SimulatorPlanPrefillStatus(
        job_id=job_id,
        finished=finished,
        result=IngestionResult(job.result).name.lower()
        if finished and job.result is not None
        else None,
        status_message=(job.meta or {}).get("status_message"),
    )


@router.get("/{plan_id}/years", response_model=list[SimulatorPlanYearRead])
async def list_simulator_plan_years(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the plan's per-year reports (with modules and stats), by year."""
    service = await _require_plan_unit_access(db, current_user, plan_id, "view")
    result = await service.list_plan_years(plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result


@router.get("/{plan_id}/aggregate-stats", response_model=dict)
async def get_simulator_plan_aggregate_stats(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Aggregate the plan's report stats into the results payload.

    ``years`` sums the per-year reports (same shape as
    ``/modules-stats/{carbon_report_id}/report-stats``, so the planner
    results chart derives from it through the same frontend adapter);
    ``grant`` carries the Project Grant report's own stats, or null —
    the two are charted side by side, never summed together (#1977).
    Per-report stats already exclude modules whose Active checkbox is off.
    """
    service = await _require_plan_unit_access(db, current_user, plan_id, "view")
    years = await service.list_plan_years(plan_id)
    if years is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    grant = next((dict(y.stats or {}) for y in years if y.is_grant), None)
    return {
        "years": merge_report_stats(
            [dict(year.stats or {}) for year in years if not year.is_grant]
        ),
        "grant": grant,
    }


@router.patch("/{plan_id}/years/{year}", response_model=SimulatorPlanYearRead)
async def set_simulator_plan_reference_year(
    plan_id: int,
    year: int,
    update: SimulatorPlanReferenceYearUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the reference (baseline) year of one plan-year report.

    All factors and prefill data of the simulation year are sourced from
    the reference year; existing entries get their emissions recomputed.
    """
    service = await _require_plan_unit_access(db, current_user, plan_id, "edit")
    try:
        updated = await service.set_reference_year(
            plan_id, year, update.reference_year, is_grant=update.is_grant
        )
    except ValueError as exc:
        # Re-snapshot of prefilled modules can fail when the new reference
        # year has no Calculator report for the unit.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan year not found")
    result, needs_prefill = updated
    await db.commit()
    result.prefill_job_id = await _enqueue_prefill(
        db, current_user, plan_id, needs_prefill
    )
    return result


@router.post(
    "/{plan_id}/duplicate",
    response_model=SimulatorPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_simulator_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Duplicate a simulator plan under the next free `<name>-N` name."""
    service = await _require_plan_unit_access(db, current_user, plan_id, "view")
    result = await service.duplicate_plan(plan_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.commit()
    return _with_can_manage(current_user, [result])[0]


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulator_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a simulator plan (and any carbon reports attached to it)."""
    service = await _require_plan_unit_access(db, current_user, plan_id, "manage")
    deleted = await service.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
