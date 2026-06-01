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

        # #1236 — capture pipeline_id as a plain value now (immutable
        # for the job's life). Read post-``finish_job`` from a fresh /
        # post-commit ``job_session`` would risk an expired-instance
        # lazy load; a local value sidesteps that entirely.
        pipeline_id_for_status = job.pipeline_id

        # Plain ``asyncio.create_task`` (not ``fire_and_forget``): the
        # local ``heartbeat_task`` ref keeps the task alive for the
        # lifetime of this function, and we cancel + await it in the
        # ``finally`` block so the cancellation is observed cleanly.
        # Routing through ``fire_and_forget`` would trip its deliberate
        # cancellation-WARNING (kept loud for diagnosing the 310-B
        # incident) on every successful run, drowning out genuine
        # cancellations.
        #
        # B-H3: ``abort_event`` is set by the heartbeat loop when
        # heartbeats have failed for long enough that the auto-recovery
        # sweep on another pod has almost certainly preempted us
        # (consecutive failures spanning ``STALE_JOB_TIMEOUT_MINUTES``).
        # The runner races handler completion against this event and,
        # if the event wins, cancels the handler so we stop burning
        # work on a row we no longer own.
        abort_event = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(job_id, abort_event),
            name=f"heartbeat-{job_id}",
        )

        try:
            handler_aborted = False
            # #1236 — initialise the chain_job deferred-dispatch queue
            # for this handler.  ``chain_job`` appends child_ids here
            # instead of firing immediately; we drain after
            # ``data_session.commit()`` so child handlers see the
            # parent's committed writes.
            from app.tasks._chain import (
                drain_pending_dispatches,
                reset_pending_dispatches,
            )

            reset_pending_dispatches()
            try:
                handler = get_handler(job_type)
                # mypy: handlers return ``Awaitable[dict]`` (registry-typed),
                # but ``asyncio.create_task`` expects ``Coroutine``.  All
                # registered handlers are async functions, so the runtime
                # value IS a coroutine — the registry's structural type just
                # widens it.
                handler_task: asyncio.Task[dict] = asyncio.create_task(
                    handler(job, job_session, data_session),  # type: ignore[arg-type]
                    name=f"handler-{job_id}",
                )
                abort_waiter = asyncio.create_task(
                    abort_event.wait(),
                    name=f"abort-waiter-{job_id}",
                )
                try:
                    done, _pending = await asyncio.wait(
                        {handler_task, abort_waiter},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    if not abort_waiter.done():
                        abort_waiter.cancel()
                        try:
                            await abort_waiter
                        except asyncio.CancelledError:
                            # Drain the cancellation we just issued — the
                            # waiter has no other failure mode worth
                            # surfacing.
                            pass

                if handler_task in done:
                    meta = handler_task.result()
                    status_message = str(meta.get("status_message", "Success"))
                    metadata = dict(meta)
                    result = meta.get("result", IngestionResult.SUCCESS)
                    handler_succeeded = True
                else:
                    # Heartbeat-driven abort: stop the handler, drop down
                    # to the rollback-and-return branch.  The new owner —
                    # the pod that recovered the stale row — will write
                    # the FINISHED row.
                    logger.error(
                        f"run_job: aborting handler for job {job_id} after "
                        "sustained heartbeat failures — another pod has "
                        "almost certainly preempted this row"
                    )
                    handler_task.cancel()
                    try:
                        await handler_task
                    except (asyncio.CancelledError, Exception):
                        # Swallow both cancellation and any exception the
                        # handler raised on the way out: we're already in
                        # the abort path and won't write its result.
                        pass
                    handler_aborted = True
                    status_message = ""
                    metadata = {}
                    result = IngestionResult.ERROR
                    handler_succeeded = False
            except Exception as exc:
                logger.exception(
                    f"run_job: handler for job_type={job_type!r} failed (job {job_id})"
                )
                status_message = str(exc)
                metadata = {}
                result = IngestionResult.ERROR
                handler_succeeded = False
                # The handler may have left ``job_session`` in a
                # PendingRollbackError state — e.g. an uncaught
                # IntegrityError from a chain_job INSERT that tripped a
                # partial unique index.  Without this rollback the
                # preempt-check (``get_job_by_id``) and ``finish_job``
                # below both run on the poisoned session, re-raise, and
                # escape this ``except`` — so the job never reaches
                # FINISHED+ERROR and stays RUNNING forever, with the
                # zombie row self-propagating the stall to every job
                # that touches it.  A clean rollback restores the
                # session for the terminal-state write.
                await job_session.rollback()

            if handler_aborted:
                # We no longer own the lock (or are about to lose it):
                # roll back the half-written data session and exit
                # without touching the job row.  The preemption check
                # below would do the same, but skipping it avoids an
                # extra DB round-trip on a path we already know is
                # exiting.
                await data_session.rollback()
                return

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
                # #1236 — drain chain_job's deferred dispatches NOW
                # that ``data_session`` is committed.  Children opened
                # fresh sessions for their reads; firing them earlier
                # races the parent's commit and they'd see stale
                # data_entries (the ones a re-upload just DELETEd) →
                # FK violation on data_entry_emissions when the
                # parent's commit lands mid-recalc.
                drain_pending_dispatches()
            else:
                await data_session.rollback()
                # Parent's writes rolled back → don't fire children
                # against a view of the world that no longer reflects
                # the parent's intent.
                from app.tasks._chain import discard_pending_dispatches

                discard_pending_dispatches()
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
                logger.warning("preempted before FINISHED write: job_id=%s", job_id)
                return

            # #1236 — advance the pipeline aggregate's authoritative
            # status. ``finish_job`` already COMMITTED job_session, so
            # this is a separate post-commit transaction: a failure
            # here CANNOT poison the durable job terminal (stronger
            # than the SAVEPOINT ideal — there is no enclosing txn
            # left to corrupt). Fully isolated: log-and-skip on any DB
            # error; the reconciliation sweep or the next sibling
            # terminal self-heals. Recompute-and-store + the
            # last-child oracle (compute_pipeline_progress.done) live
            # in ``recompute_pipeline_status``.
            #
            # NOTE for future handler authors: this write reuses
            # ``job_session`` — the SAME connection the handler ran on.
            # It is in a clean post-commit state here, but a handler
            # that leaves connection-level artifacts (advisory locks,
            # server-side temp state) would silently leak them into
            # this write. No current handler does; if you add one that
            # does, give the status write its own session.
            if pipeline_id_for_status is not None:
                try:
                    await repo.recompute_pipeline_status(pipeline_id_for_status)
                    await job_session.commit()
                except Exception:
                    logger.exception(
                        "run_job: pipeline status recompute failed — "
                        "skipped, sweep will heal (job_id=%s "
                        "pipeline_id=%s)",
                        job_id,
                        pipeline_id_for_status,
                    )
                    await job_session.rollback()
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                # Expected — we cancelled it ourselves.
                pass


async def _heartbeat_loop(job_id: int, abort_event: asyncio.Event) -> None:
    """Refresh ``locked_at`` on the active job until cancelled.

    Wake every ``STALE_JOB_TIMEOUT_MINUTES / 4`` (default: every
    15 min for a 60 min timeout) and call ``repo.heartbeat``.  If
    the heartbeat returns 0 rows updated, our lock has been preempted
    — exit the loop so the runner's preemption check can take over
    on its next pass.

    Each tick uses a fresh session: heartbeats fire concurrently
    with the handler's session, so sharing would deadlock or
    serialize on the underlying connection.

    B-H3: count consecutive heartbeat exceptions.  If they span
    ``STALE_JOB_TIMEOUT_MINUTES`` (i.e. the auto-recovery sweep's
    threshold), set ``abort_event`` so the runner cancels the handler
    — by then another pod's stale-recovery sweep has almost certainly
    re-claimed this row, and continuing to run the handler would
    burn duplicate work that Unit 1's CAS will only be able to drop
    at the very end.  Successful heartbeats reset the counter.
    """
    settings = get_settings()
    interval_seconds = max(1.0, settings.STALE_JOB_TIMEOUT_MINUTES * 60 / 4)
    # Threshold: enough consecutive failures to span the stale-job
    # window.  ``max(1, ...)`` so a tiny mis-configured interval still
    # gives the loop one chance to recover before aborting.
    failure_threshold = max(
        1, int(settings.STALE_JOB_TIMEOUT_MINUTES * 60 / interval_seconds)
    )
    consecutive_failures = 0
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
            consecutive_failures = 0
        except asyncio.CancelledError:
            # Normal shutdown path — the runner cancels us in its
            # ``finally`` block.  Re-raise so asyncio sees the
            # cancellation cleanly.
            raise
        except Exception as exc:
            # Don't let a transient DB hiccup kill the heartbeat;
            # log and try again next interval.  But if failures span
            # the stale-job window, signal the runner to abort: the
            # row is almost certainly owned by another pod now.
            consecutive_failures += 1
            logger.warning(
                f"_heartbeat_loop: heartbeat for job {job_id} failed "
                f"({consecutive_failures}/{failure_threshold}): {exc}"
            )
            if consecutive_failures >= failure_threshold:
                logger.error(
                    f"_heartbeat_loop: heartbeat for job {job_id} failed "
                    f"{consecutive_failures} consecutive times "
                    f"(>= {failure_threshold}, spanning "
                    f"STALE_JOB_TIMEOUT_MINUTES={settings.STALE_JOB_TIMEOUT_MINUTES}) "
                    "— signalling runner to abort handler"
                )
                abort_event.set()
                return
