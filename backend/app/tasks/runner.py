"""Plan 310-C unified job runner.

The runner is the single dispatch path for every Plan 310-C
``DataIngestionJob``.  Endpoints, the safety poller, and
``app.tasks._chain.chain_job`` all funnel through ``run_job(job_id)``;
the registry resolves the correct handler from ``job.job_type``.

Why a single dispatcher:

- **One claim path** — every job goes through ``claim_job``, so the
  pod-safety guarantees from Plan 310-A (atomic state→RUNNING +
  attempts++ + locked_by + ``started_at`` stamping) apply uniformly.
- **One observability path** — every job ends with the same
  ``finish_job(...)`` CAS call (B-C1), which auto-stamps
  ``finished_at`` (Plan 310-C observability columns).  Dashboard
  queries that rely on ``finished_at IS NOT NULL`` see every job.
- **One preemption-safety story** — the heartbeat + worker-side
  preemption check eliminate the duplicate-processing risk that the
  safety poller's stale-recovery sweep introduced (PR #998 review).

Concurrency model per ``run_job`` invocation:

- Two SQLModel sessions: ``job_session`` for the
  ``DataIngestionJob`` row's lifecycle, ``data_session`` for the
  handler's domain writes.  Separate so a handler ``rollback`` does
  not roll back the FINISHED+ERROR state-write the runner makes
  afterward.
- One per-job heartbeat task that wakes every
  ``STALE_JOB_TIMEOUT_MINUTES / 4`` and refreshes ``locked_at`` via
  its OWN session.  Cancelled in ``finally`` regardless of outcome
  (handler success, handler raise, preemption).
"""

import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import (
    IngestionResult,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._pod_id import POD_ID
from app.tasks.registry import get_handler

logger = get_logger(__name__)


async def run_job(job_id: int) -> None:
    """Dispatch a job through its registered handler.

    Single entry point used by:
      - HTTP endpoints (``fire_and_forget(run_job(id))`` after creating a job)
      - ``app.tasks._chain.chain_job`` (parent handler chains a child)
      - the safety poller (orphan recovery)

    Lifecycle:

      1. Open job_session + data_session.
      2. Resolve job → reject if missing or ``job_type IS NULL``.
      3. ``claim_job`` (atomic RUNNING + attempts++ + ``started_at``).
         Returns False if the job was already claimed / finished /
         out of retries — in which case run_job is a silent no-op.
      4. Spawn heartbeat task (refreshes ``locked_at`` periodically).
      5. Look up handler from registry → execute it.
      6. Pre-commit preemption check: re-read the row; if
         ``locked_by`` no longer equals our pod, roll back the
         data_session and exit without state-changing the job (the
         new owner will).
      7. Commit data_session, ``finish_job`` (atomic CAS on
         ``locked_by`` + ``state=RUNNING``) to FINISHED+SUCCESS
         (or FINISHED+ERROR on handler raise).  CAS no-op return
         means a stale-lock sweep preempted us between step 6 and
         step 7 — log+exit, the new owner will close the row.
      8. ``finish_job`` stamps ``finished_at`` via ``coalesce``
         (Plan 310-C observability), so the dashboard duration
         query (finished_at - started_at) closes cleanly.
      9. Cancel heartbeat task in ``finally``.

    Errors raised by the handler are caught and persisted as
    FINISHED+ERROR.  Errors raised by the runner itself (claim
    contention, preemption) are logged and the job state is left for
    the next claimer.
    """
    # Plan 310-C: ensure every handler module has been imported so the
    # registry is populated before lookup.  Idempotent — first call
    # imports, subsequent calls are a no-op.  Lazy import (here, not at
    # module top) avoids the circular import via audit_service →
    # audit_sync_tasks → app.tasks.__init__ → ingestion_tasks → providers
    # → audit_service.
    from app.tasks.bootstrap import bootstrap_handlers

    bootstrap_handlers()

    async with SessionLocal() as job_session, SessionLocal() as data_session:
        repo = DataIngestionRepository(job_session)

        job = await repo.get_job_by_id(job_id)
        if job is None:
            logger.error(f"run_job: job {job_id} not found")
            return
        if job.job_type is None:
            logger.error(
                f"run_job: job {job_id} has no job_type — refusing to dispatch"
            )
            return

        # Capture job_type while it's narrowed to ``str`` by the
        # check above; the post-claim re-fetch widens it back to
        # ``Optional[str]`` (claim_job never touches job_type, so this
        # is a type-narrowing convenience, not a behavior change).
        job_type: str = job.job_type

        if not await repo.claim_job(job_id, POD_ID):
            # Another pod beat us, attempts exhausted, or the row is
            # already FINISHED.  Either way: not ours to run.
            return

        # ``claim_job`` ran a raw SQL UPDATE (state=RUNNING, attempts++,
        # locked_by, locked_at, and — via the func.coalesce from PR #1026
        # — started_at).  The in-memory ``job`` instance from the pre-claim
        # ``get_job_by_id`` still reflects the OLD row, so re-fetch to
        # hand handlers the authoritative post-claim state (state, attempts,
        # locked_by, started_at).  ``get_job_by_id`` already calls refresh.
        job = await repo.get_job_by_id(job_id)
        if job is None:
            # Race: claimed but row vanished before the re-read.  Treat
            # as preempted and exit; no state to write since there's no
            # row to write to.
            logger.warning(f"run_job: job {job_id} disappeared after claim — exiting")
            return

        # Plain ``asyncio.create_task`` (not ``fire_and_forget``): the
        # local ``heartbeat_task`` ref keeps the task alive for the
        # lifetime of this function, and we cancel + await it in the
        # ``finally`` block so the cancellation is observed cleanly.
        # Routing through ``fire_and_forget`` would trip its deliberate
        # cancellation-WARNING (kept loud for diagnosing the 310-B
        # incident) on every successful run, drowning out genuine
        # cancellations.
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(job_id),
            name=f"heartbeat-{job_id}",
        )

        try:
            try:
                handler = get_handler(job_type)
                meta = await handler(job, job_session, data_session)
                status_message = str(meta.get("status_message", "Success"))
                metadata = dict(meta)
                result = meta.get("result", IngestionResult.SUCCESS)
                handler_succeeded = True
            except Exception as exc:
                logger.exception(
                    f"run_job: handler for job_type={job_type!r} failed (job {job_id})"
                )
                status_message = str(exc)
                metadata = {}
                result = IngestionResult.ERROR
                handler_succeeded = False

            # Preemption check covers BOTH success and error paths: if a
            # stale-lock sweep recovered this row mid-handler, a different
            # pod may now own it.  Either way, our writes — successful or
            # error — must NOT race with the new owner's run.  Roll back
            # data and skip the state update; the new owner will close out.
            current = await repo.get_job_by_id(job_id)
            if current is None or current.locked_by != POD_ID:
                logger.warning(
                    f"run_job: job {job_id} preempted "
                    f"(locked_by={current and current.locked_by!r}); "
                    "rolling back data writes and exiting without "
                    "updating job state"
                )
                await data_session.rollback()
                return

            if handler_succeeded:
                await data_session.commit()
            else:
                await data_session.rollback()
            # Plan 310 review finding B-C1: the FINISHED write must be a
            # compare-and-set on ``(locked_by=POD_ID AND state=RUNNING)``,
            # not a blind UPDATE.  The pre-handler preempt-check at line
            # 166 catches the common case, but a stale-lock sweep between
            # that check and the UPDATE below would otherwise let this
            # pod clobber the new owner's RUNNING row with our FINISHED
            # write.  ``finish_job`` returns False in that race; we log
            # and exit cleanly so the new owner can close the row.
            wrote = await repo.finish_job(
                job_id,
                POD_ID,
                result=result,
                status_message=status_message,
                metadata=metadata,
            )
            if not wrote:
                logger.warning(
                    "preempted before FINISHED write: job_id=%s", job_id
                )
                return
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                # Expected — we cancelled it ourselves.
                pass


async def _heartbeat_loop(job_id: int) -> None:
    """Refresh ``locked_at`` on the active job until cancelled.

    Wake every ``STALE_JOB_TIMEOUT_MINUTES / 4`` (default: every
    15 min for a 60 min timeout) and call ``repo.heartbeat``.  If
    the heartbeat returns 0 rows updated, our lock has been preempted
    — exit the loop so the runner's preemption check can take over
    on its next pass.

    Each tick uses a fresh session: heartbeats fire concurrently
    with the handler's session, so sharing would deadlock or
    serialize on the underlying connection.
    """
    settings = get_settings()
    interval_seconds = max(1.0, settings.STALE_JOB_TIMEOUT_MINUTES * 60 / 4)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with SessionLocal() as session:
                repo = DataIngestionRepository(session)
                updated = await repo.heartbeat(job_id, POD_ID)
                if updated == 0:
                    logger.warning(
                        f"_heartbeat_loop: lost lock on job {job_id} "
                        "(preempted or state moved out of RUNNING) — "
                        "stopping heartbeat"
                    )
                    return
        except asyncio.CancelledError:
            # Normal shutdown path — the runner cancels us in its
            # ``finally`` block.  Re-raise so asyncio sees the
            # cancellation cleanly.
            raise
        except Exception as exc:
            # Don't let a transient DB hiccup kill the heartbeat;
            # log and try again next interval.
            logger.warning(f"_heartbeat_loop: heartbeat for job {job_id} failed: {exc}")
