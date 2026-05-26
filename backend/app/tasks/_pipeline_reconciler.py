"""In-process pipeline-status reconciliation sweep (#1236 Phase 3).

The runner writes ``pipelines.status`` post-``finish_job`` on an isolated
session that **log-and-skips** on any DB error so a transient failure
can't poison the job's terminal state.  That safety net leaves a small
window where ``pipelines.status`` lags the real chain state.

This sweep is the durable backstop: every ``PIPELINE_RECONCILER_INTERVAL_SECONDS``
(default 60s) it walks pipelines, recomputes status from current job
rows, and writes the corrected value.  Idempotent — re-running on a
healthy DB is a no-op.

Same loop hygiene as ``_poller``: session per iteration (the repo
already commits per pipeline; pinning a pool slot for the whole loop
would starve other readers), broad ``except`` so one iteration's
failure doesn't kill the loop, settings flag for the diagnostic
"let the table lag" case.

Multi-pod note: every pod runs this sweep concurrently.  That's safe
because ``recompute_pipeline_status`` is idempotent and commits per
row — no advisory lock needed.  If contention is ever measured, add
jitter; until then, YAGNI.
"""

import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import IngestionMethod, TargetType
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._chain import AGGREGATION_DEDUP, chain_job

logger = get_logger(__name__)


async def _recover_orphan_aggregations() -> int:
    """Backfill aggregation jobs for pipelines whose coalescing gate
    stalled.

    See ``DataIngestionRepository.find_orphan_aggregation_pipelines``
    for the precise definition.  This function pairs the discovery
    with the dispatch: for each orphan, pick any recalc sibling as
    the parent, call ``chain_job`` (which writes the aggregation row
    and fire-and-forgets ``run_job``), and commit.  Each orphan is
    its own transaction so a mid-sweep failure keeps earlier fixes.

    Returns the number of aggregation jobs actually dispatched.
    """
    fired = 0
    async with SessionLocal() as session:
        repo = DataIngestionRepository(session)
        orphans = await repo.find_orphan_aggregation_pipelines()
        for pid in orphans:
            # Pick a sibling as the chain parent. ``chain_job`` only
            # reads its ``pipeline_id`` / ``module_type_id`` / ``year``
            # — any FINISHED recalc sibling carries the same values.
            siblings = await repo.list_jobs_by_pipeline_id(pid)
            recalc_siblings = [s for s in siblings if s.job_type == "emission_recalc"]
            if not recalc_siblings:
                continue
            parent = recalc_siblings[0]
            try:
                # ``dedup_config=AGGREGATION_DEDUP`` is the safety net
                # if two pods race the sweep on the same pipeline —
                # the partial unique index covers NOT_STARTED/QUEUED/
                # RUNNING aggregation rows so only the first INSERT
                # wins; the second is dropped by the dedup pre-check
                # or the IntegrityError it surfaces.
                child_id = await chain_job(
                    parent,
                    job_type="aggregation",
                    module_type_id=parent.module_type_id,
                    year=parent.year,
                    ingestion_method=IngestionMethod.computed,
                    target_type=TargetType.DATA_ENTRIES,
                    session=session,
                    dedup_config=AGGREGATION_DEDUP,
                )
                await session.commit()
                if child_id is not None:
                    fired += 1
                    logger.info(
                        "Pipeline reconciler backfilled orphan aggregation: "
                        "pipeline_id=%s parent_recalc_id=%s child_id=%s",
                        pid,
                        parent.id,
                        child_id,
                    )
            except Exception:
                # Per-pipeline isolation: one orphan's failure (e.g.
                # transient FK violation, dedup race) mustn't block
                # the others.
                logger.exception(
                    "Pipeline reconciler failed to backfill orphan "
                    "aggregation for pipeline_id=%s",
                    pid,
                )
                await session.rollback()
    return fired


async def reconcile_pipeline_statuses_loop() -> None:
    """Run the reconciliation sweep on the configured cadence forever.

    Cancellation: ``asyncio.CancelledError`` propagates out of the
    ``asyncio.sleep`` — the lifespan shutdown awaits this loop's
    cancellation explicitly (see ``app.main.lifespan``).
    """
    settings = get_settings()
    interval = settings.PIPELINE_RECONCILER_INTERVAL_SECONDS
    while True:
        try:
            async with SessionLocal() as session:
                repo = DataIngestionRepository(session)
                summary = await repo.reconcile_pipeline_statuses()
            if summary.get("corrected"):
                # Only log when the sweep had to fix something — a
                # quiet sweep is the common case and would otherwise
                # spam the logs.
                logger.info(
                    "Pipeline reconciler healed %s/%s pipeline(s)",
                    summary["corrected"],
                    summary["checked"],
                )
            # Orphan-aggregation backfill (#1080 follow-up, 2026-05-21
            # stuck-recalc bug).  Independent of the status recompute —
            # it fixes a DIFFERENT class of stall (the coalescing-gate
            # gap), and the two healing actions naturally compose on
            # the same sweep cadence.
            fired = await _recover_orphan_aggregations()
            if fired:
                logger.info(
                    "Pipeline reconciler backfilled %s orphan aggregation(s)",
                    fired,
                )
        except Exception as exc:
            logger.warning(
                f"Pipeline reconciler iteration failed: {exc}",
                exc_info=True,
            )
        await asyncio.sleep(interval)
