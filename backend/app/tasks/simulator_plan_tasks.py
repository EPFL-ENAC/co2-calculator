"""Simulator-plan prefill job (plan #2050 Track F4).

Copying a reference year into a plan year is the expensive half of both
plan PATCHes: a 10-year range over a large baseline runs to tens of
thousands of ``data_entries`` plus their emissions, measured at 21.9s on
dev for a single year of a ~5k-entry module. The routes now persist only
the cheap metadata change and hand the copy to this handler.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import DataIngestionJob
from app.services.simulator_plan_service import SimulatorPlanService
from app.tasks.registry import register

logger = get_logger(__name__)


@register("simulator_plan_prefill")
async def simulator_plan_prefill_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Prefill the reports listed in ``meta.config.report_ids``.

    The runner has already claimed the job (state=RUNNING, attempts++,
    started_at stamped) and commits ``data_session`` once this returns —
    this handler must not write the FINISHED state itself.

    Safe to re-run after a crashed or preempted job: prefill empties each
    module before rebuilding it, so a retry converges rather than
    duplicating rows.
    """
    if job.id is None:
        raise ValueError("simulator_plan_prefill: job has no id")
    config = (job.meta or {}).get("config") or {}
    report_ids = config.get("report_ids") or []
    plan_id = config.get("plan_id")
    if not report_ids:
        raise ValueError(
            f"simulator_plan_prefill job {job.id} has no report_ids to prefill"
        )

    service = SimulatorPlanService(data_session)
    prefilled = await service.prefill_reports([int(r) for r in report_ids])
    logger.info(
        f"simulator_plan_prefill (job {job.id}): prefilled {prefilled} "
        f"report(s) of plan {plan_id}"
    )
    return {
        "status_message": f"Prefilled {prefilled} plan year(s)",
        "result": {"plan_id": plan_id, "reports_prefilled": prefilled},
    }
