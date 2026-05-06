"""Background task — Plan 310-D ``aggregation`` handler.

Owns ``carbon_reports.stats`` writes for the bulk path.  After
``emission_recalc`` finishes writing the underlying ``data_entry_emissions``
rows, the recalc handler chains to ``aggregation`` for the scope
``(module_type_id, year)``; this handler walks every ``CarbonReportModule``
in that slice and calls ``CarbonReportModuleService.recompute_stats``,
which is the same code Path 1 (manual edits) calls inline.

Additive in this PR — no caller invokes this handler yet.  The cutover
PR (`emission_recalc_handler` chains here, providers stop calling
``recompute_stats`` directly) lands next in the Plan-D Tier-2 sequence.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import DataIngestionJob, IngestionResult
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.tasks.registry import register

logger = get_logger(__name__)


@register("aggregation")
async def aggregation_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Plan 310-D handler — sole writer of ``carbon_reports.stats`` for the
    bulk path.

    Reads scope ``(module_type_id, year)`` from the job row.  Walks every
    ``CarbonReportModule`` in that slice and invokes
    ``CarbonReportModuleService.recompute_stats``, which reads
    ``data_entry_emissions`` for the module, rebuilds the stats JSON, and
    persists it (with the parent ``CarbonReport.stats`` rollup as a
    side-effect of the existing service implementation).

    The runner has already claimed the job (state=RUNNING, attempts++,
    started_at stamped).  This handler does not call ``claim_job`` and
    must not write the FINISHED state — both belong to ``run_job``.

    Returns the meta dict the runner persists on the FINISHED-state write.
    ``status_message`` and ``result`` keys are read by the runner.
    """
    if job.id is None:
        raise ValueError("aggregation: job has no id")
    if job.module_type_id is None or job.year is None:
        raise ValueError(f"aggregation job {job.id} missing module_type_id or year")

    svc = CarbonReportModuleService(data_session)
    affected = await svc.list_modules_for(
        module_type_id=job.module_type_id, year=job.year
    )

    logger.info(
        f"aggregation handler (job {job.id}): recomputing stats for "
        f"{len(affected)} module(s) "
        f"in scope module_type_id={job.module_type_id}/year={job.year}"
    )

    for module in affected:
        if module.id is None:
            # Defensive: rows fetched from DB always have ids, but the
            # SQLModel field is Optional[int] so mypy needs the guard.
            continue
        await svc.recompute_stats(module.id)

    return {
        "status_message": "Aggregation completed",
        "result": IngestionResult.SUCCESS,
        "modules_refreshed": len(affected),
    }
