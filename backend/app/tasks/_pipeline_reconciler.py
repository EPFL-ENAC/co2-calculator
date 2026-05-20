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
from app.repositories.data_ingestion import DataIngestionRepository

logger = get_logger(__name__)


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
        except Exception as exc:
            logger.warning(
                f"Pipeline reconciler iteration failed: {exc}",
                exc_info=True,
            )
        await asyncio.sleep(interval)
