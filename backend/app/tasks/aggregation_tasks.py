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

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import DataIngestionJob, IngestionResult
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.tasks.registry import register

# #1236 Phase 4A.2 — per-year advisory-lock namespace. Using the
# 2-int variant ``pg_advisory_xact_lock(category, year)`` so the lock
# space is namespaced and can't collide with unrelated advisory-lock
# users in the same DB.
_AGGREGATION_LOCK_CATEGORY = 1236

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

    # #1236 Phase 4A.2 — per-year transaction-scoped advisory lock.
    # Cross-pipeline aggregations of the SAME year all touch the same
    # ``carbon_reports.stats`` rows (one per unit) as a side-effect of
    # ``recompute_stats``; without serialisation Postgres deadlocks
    # them (the exact pattern in jobs 44/90/101 of the localhost
    # dump). ``pg_advisory_xact_lock`` serialises them at the lock,
    # not at the dedup index — so no drop-hazard (the existing
    # AGGREGATION_DEDUP partial unique index would silently cancel
    # the loser if widened to year-only scope; this approach avoids
    # that). The lock is held until ``data_session`` commits or rolls
    # back (the runner does that after the handler returns).
    #
    # Dialect-gated so the SQLite test fixture (and mock-driven unit
    # tests) skip cleanly — SQLite's single-writer model already
    # serialises any concurrent writers, so the lock is a no-op there.
    try:
        dialect_name = data_session.get_bind().dialect.name
    except Exception:
        dialect_name = ""
    if dialect_name == "postgresql":
        await data_session.execute(
            text("SELECT pg_advisory_xact_lock(:cat, :year)"),
            {"cat": _AGGREGATION_LOCK_CATEGORY, "year": int(job.year)},
        )
        logger.debug(
            f"aggregation handler (job {job.id}): acquired "
            f"pg_advisory_xact_lock({_AGGREGATION_LOCK_CATEGORY}, {job.year})"
        )

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
