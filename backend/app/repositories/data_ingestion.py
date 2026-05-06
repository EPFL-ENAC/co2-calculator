import enum
from datetime import datetime, timedelta, timezone
from typing import List, Optional, TypedDict
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, desc, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)

logger = get_logger(__name__)


class _ClaimUnavailable(Exception):
    """Internal sentinel — Step 2 of claim_job matched no row.

    Raised inside ``begin_nested()`` to trigger SAVEPOINT rollback so Step 1's
    demote is undone without disturbing the outer transaction.
    """


class DataIngestionRepository:
    """Repository for DataIngestionJob database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ingestion_job(
        self,
        data: DataIngestionJob,
    ) -> DataIngestionJob:
        job = DataIngestionJob.model_validate(data)
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    def sanitize_for_json(self, obj):
        if isinstance(obj, dict):
            return {
                k: self.sanitize_for_json(v)
                for k, v in obj.items()
                if not (
                    isinstance(k, str)
                    and (k.startswith("_") or k == "_sa_instance_state")
                )
            }
        elif isinstance(obj, list):
            return [self.sanitize_for_json(i) for i in obj]
        elif isinstance(obj, enum.Enum):
            return obj.value
        else:
            return obj

    async def update_ingestion_job(
        self,
        job_id: int,
        status_message: str,
        metadata: dict,
        completed_at: Optional[datetime] = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
    ) -> Optional[DataIngestionJob]:
        """Update ingestion job's status_message, state, result, and metadata.

        ``state == FINISHED`` also auto-stamps the top-level ``finished_at``
        column when it is still NULL (see the ``state`` arg below).

        Args:
            job_id: Job ID to update
            status_message: Status message
            metadata: Metadata to merge
            completed_at: Optional completed timestamp written into ``meta``
                (legacy JSON field; pre-dates the ``finished_at`` column).
            state: New state value (optional, for new code).  When this
                transitions the row to ``FINISHED`` and ``finished_at`` is
                still NULL, the column is auto-stamped (idempotent — a
                later update keeps the original timestamp).
            result: New result value (optional, for new code)
        """
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        exec_result = await self.session.execute(stmt)
        result_job = exec_result.scalar_one_or_none()
        if not result_job:
            return None

        if result_job:
            DataIngestionJob.model_validate(result_job)

            result_job.status_message = status_message
            if state is not None:
                result_job.state = state
            if result is not None:
                result_job.result = result
            if state == IngestionState.FINISHED and result_job.finished_at is None:
                # Auto-stamp on the FIRST transition to FINISHED.  IS NULL
                # guard makes it idempotent — re-running update on an
                # already-FINISHED row leaves the original timestamp intact.
                # Server-side ``func.now()`` matches claim_job's locked_at.
                result_job.finished_at = func.now()

            merged_meta = {
                **self.sanitize_for_json(result_job.meta or {}),
                **self.sanitize_for_json(metadata or {}),
                "completed_at": (
                    completed_at.isoformat()
                    if completed_at
                    else (
                        datetime.now(timezone.utc).isoformat()
                        if state in (IngestionState.FINISHED,)
                        else None
                    )
                ),
            }
            result_job.meta = merged_meta
            await self.session.flush()
            await self.session.refresh(result_job)
        return result_job

    async def heartbeat(self, job_id: int, pod_id: str) -> int:
        """Refresh ``locked_at`` on a RUNNING job we still own.

        The Plan 310-C runner spawns a heartbeat task per active job that
        wakes every ``STALE_JOB_TIMEOUT_MINUTES / 4`` and calls this
        method.  Without it, the safety poller's stale-lock sweep would
        falsely classify any legitimately long-running job as a crashed
        pod once its runtime exceeds the timeout window — leading to the
        same row being claimed by a second pod.

        The WHERE clause guards against three failure modes:

        - ``locked_by == pod_id`` — refuse to refresh someone else's
          lock if a sweep already preempted us; the next preemption
          check in the runner will then exit cleanly.
        - ``state == RUNNING`` — refuse to revive a row that the runner
          (or an admin) already moved out of RUNNING (cancelled,
          finished, recovered).

        Returns the rowcount actually updated (0 or 1) so the caller
        can detect preemption and stop the heartbeat loop.
        """
        result = await self.session.execute(
            update(DataIngestionJob)
            .where(
                col(DataIngestionJob.id) == job_id,
                col(DataIngestionJob.locked_by) == pod_id,
                col(DataIngestionJob.state) == IngestionState.RUNNING,
            )
            .values(locked_at=func.now())
        )
        await self.session.commit()
        # ``rowcount`` is a SQLAlchemy ``Result`` attribute populated by
        # the UPDATE driver — Pyright's stubs don't expose it, so guard
        # via ``hasattr`` (matches the pattern in ``mark_job_as_current``).
        if result is not None and hasattr(result, "rowcount"):
            return int(result.rowcount or 0)
        return 0

    async def set_started_at(self, job_id: int) -> None:
        """Stamp ``started_at`` on the FIRST successful claim only.

        Idempotent via the ``started_at IS NULL`` guard — retries (every
        subsequent claim_job after the original pod crashed and the safety
        sweep recovered the row) call this again but the UPDATE matches no
        row, leaving the original timestamp intact.  This is the property
        that lets ``finished_at - started_at`` measure total wall-clock
        duration across retries; ``locked_at`` (refreshed on every claim)
        answers a different question.

        Does not commit — leaves transaction control to the caller (the
        ``run_job`` runner in Plan 310C), matching ``update_ingestion_job``.
        """
        await self.session.execute(
            update(DataIngestionJob)
            .where(
                col(DataIngestionJob.id) == job_id,
                col(DataIngestionJob.started_at).is_(None),
            )
            .values(started_at=func.now())
        )

    async def get_job_by_id(self, job_id: int) -> Optional[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        exec_result = await self.session.execute(stmt)
        job = exec_result.scalar_one_or_none()
        if job:
            await self.session.refresh(job)
        return job

    async def get_jobs_by_year(self, year: int) -> List[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.year == year)
        stmt = stmt.order_by(col(DataIngestionJob.id).desc())
        exec_result = await self.session.execute(stmt)
        return list(exec_result.scalars().all())

    async def list_jobs_by_pipeline_id(
        self, pipeline_id: UUID
    ) -> List[DataIngestionJob]:
        """Return every job that shares the given ``pipeline_id``.

        Plan 310C — backs the ``GET /sync/pipelines/{pipeline_id}`` endpoint
        so dashboards can render the whole multi-step run (parent + fan-out
        children seeded by ``_enqueue_stale_recalculations``) in id order.

        ``populate_existing=True`` is required for Plan 310D's SSE polling
        endpoint (``GET /sync/pipelines/{pipeline_id}/stream``): the runner
        writes job state changes (claim, FINISHED, status_message) on its
        OWN ``SessionLocal()`` connection, so without this flag SQLAlchemy's
        identity map would serve the SSE session a stale cached row on
        every poll and the change-detection (``snapshot != last_snapshot``)
        would never fire.  The one-shot read endpoint pays no cost for the
        flag (its session lives one request), so we set it here rather than
        plumbing a ``populate_existing`` kwarg through.
        """
        stmt = (
            select(DataIngestionJob)
            .where(DataIngestionJob.pipeline_id == pipeline_id)
            .order_by(col(DataIngestionJob.id).asc())
            .execution_options(populate_existing=True)
        )
        exec_result = await self.session.execute(stmt)
        return list(exec_result.scalars().all())

    async def get_current_pipeline_id_for_module(
        self,
        module_type_id: int,
        year: Optional[int] = None,
    ) -> Optional[UUID]:
        """Return the most recent active pipeline whose any-job touches
        the given ``module_type_id`` (and optionally ``year``).

        Plan 310-D — backs the ``CarbonReportModuleRead.current_pipeline_id``
        field so the frontend can show a "Recalculating..." badge while
        a bulk pipeline is in flight.  "Active" means a non-terminal
        state: ``NOT_STARTED``, ``QUEUED``, or ``RUNNING``.  ``FINISHED``
        and any ``CANCELLED``/error states are excluded — once the
        terminal write lands, the badge clears.

        We scope by ``module_type_id`` (and year, for the read endpoint
        that's already keyed by year) and pick the **most recent** one
        by job id when multiple active pipelines exist (rare but possible
        — e.g. if a follow-up factor sync chains while an earlier ingest
        chain is still aggregating).  The frontend subscribes to a
        single pipeline, so returning more than one would force the
        caller to pick anyway.

        ``pipeline_id`` is allowed to be NULL on legacy rows; the
        ``isnot(None)`` guard ensures we only consider chained jobs.

        Returns ``None`` when no active pipeline matches.

        Resolved during the dev-rebase of PR #1053 (PR5) on top of #1052:
        PR5 needs the optional ``year`` filter for the carbon-report
        service caller, which is keyed by year.  Strict superset of #1052's
        signature — when ``year=None`` the filter is omitted, matching
        the original behavior.
        """
        stmt = (
            select(DataIngestionJob.pipeline_id)
            .where(
                col(DataIngestionJob.module_type_id) == module_type_id,
                col(DataIngestionJob.pipeline_id).isnot(None),
                col(DataIngestionJob.state).in_(
                    [
                        IngestionState.NOT_STARTED,
                        IngestionState.QUEUED,
                        IngestionState.RUNNING,
                    ]
                ),
            )
            .order_by(col(DataIngestionJob.id).desc())
            .limit(1)
        )
        if year is not None:
            stmt = stmt.where(col(DataIngestionJob.year) == year)

        exec_result = await self.session.execute(stmt)
        row = exec_result.first()
        if row is None:
            return None
        return row[0]

    # ---- Plan 310A: atomic claim, recovery, poller helpers ----

    def _build_combo_where(self, job: DataIngestionJob):
        """Build WHERE clause for the same module/det/target/method/year combo."""
        where = and_(
            col(DataIngestionJob.target_type) == job.target_type,
            col(DataIngestionJob.ingestion_method) == job.ingestion_method,
            col(DataIngestionJob.year) == job.year,
        )
        if job.module_type_id is None:
            where = and_(where, col(DataIngestionJob.module_type_id).is_(None))
        else:
            where = and_(
                where, col(DataIngestionJob.module_type_id) == job.module_type_id
            )
        if job.data_entry_type_id is None:
            where = and_(where, col(DataIngestionJob.data_entry_type_id).is_(None))
        else:
            where = and_(
                where,
                col(DataIngestionJob.data_entry_type_id) == job.data_entry_type_id,
            )
        return where

    async def claim_job(self, job_id: int, pod_id: str) -> bool:
        """Atomically claim a job for execution.

        Two-step transaction:
        1. Unset is_current on previous current row (if any) for the same combo.
        2. Atomic UPDATE that flips to RUNNING + is_current + locked_by.
           The partial unique index trips here if a concurrent claimer already set
           is_current=TRUE on a different row for the same combo.

        Returns True if claimed, False otherwise.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return False

        # Wrap both steps in a SAVEPOINT so a failed Step 2 rolls back
        # Step 1's demote without touching the outer transaction.  Without
        # this, an unsuccessful claim (locked, attempts exhausted, run_after
        # in future, …) would silently strip the previous is_current sibling
        # of its current marker.
        try:
            async with self.session.begin_nested():
                # Step 1 — clear previous is_current for the same combo,
                # but only for siblings that are NOT currently RUNNING.
                # Demoting a RUNNING sibling would let two pods process
                # the same combo concurrently — the partial unique index
                # can't catch it once the demote commits.
                combo_where = and_(
                    col(DataIngestionJob.is_current),
                    col(DataIngestionJob.id) != job_id,
                    col(DataIngestionJob.state) != IngestionState.RUNNING,
                    self._build_combo_where(job),
                )
                await self.session.execute(
                    update(DataIngestionJob).where(combo_where).values(is_current=False)
                )

                # Step 2 — atomic claim
                result = await self.session.execute(
                    update(DataIngestionJob)
                    .where(
                        col(DataIngestionJob.id) == job_id,
                        col(DataIngestionJob.state).in_(
                            [IngestionState.NOT_STARTED, IngestionState.QUEUED]
                        ),
                        col(DataIngestionJob.locked_by).is_(None),
                        col(DataIngestionJob.attempts)
                        < col(DataIngestionJob.max_attempts),
                        or_(
                            col(DataIngestionJob.run_after).is_(None),
                            col(DataIngestionJob.run_after) <= func.now(),
                        ),
                    )
                    .values(
                        locked_by=pod_id,
                        locked_at=func.now(),
                        # Stamp ``started_at`` atomically with the RUNNING
                        # transition so a crash between this commit and the
                        # runner doing work cannot leave the column NULL.
                        # ``coalesce`` preserves the original timestamp on
                        # retry-claim — ``finished_at - started_at`` then
                        # measures total wall-clock duration across retries.
                        started_at=func.coalesce(
                            col(DataIngestionJob.started_at), func.now()
                        ),
                        state=IngestionState.RUNNING,
                        is_current=True,
                        attempts=col(DataIngestionJob.attempts) + 1,
                    )
                    .returning(col(DataIngestionJob.id))
                )
                if result.scalar_one_or_none() is None:
                    raise _ClaimUnavailable
        except _ClaimUnavailable:
            return False
        except IntegrityError:
            return False

        await self.session.commit()
        return True

    async def sweep_stuck_running_jobs(
        self, stale_timeout_minutes: int
    ) -> tuple[int, int]:
        """Auto-recovery sweep for jobs stuck in RUNNING after a pod crash.

        The poller calls this once per tick.  Jobs whose ``locked_at`` is
        older than the stale window are split into two buckets:

        - **Recoverable** (``attempts < max_attempts``) — reset to
          NOT_STARTED so the next poll cycle can re-dispatch them.  Unlike
          ``recover_job`` (the manual API path, which resets ``attempts=0``
          on operator intent), this preserves ``attempts`` so a genuinely
          broken job that crashes every claim can't loop forever — once
          ``attempts`` reaches ``max_attempts`` the next sweep abandons it.

        - **Abandoned** (``attempts >= max_attempts``) — moved to
          ``state=FINISHED, result=ERROR`` with a diagnostic
          ``status_message``.  Operators see the failure on the dashboard
          instead of a silently-stuck row.

        Returns ``(recovered_count, abandoned_count)``.

        ⚠️ **No heartbeat (yet)**: ``locked_at`` is set ONCE by
        ``claim_job`` and never refreshed during execution, so any
        legitimately long-running job whose runtime exceeds
        ``stale_timeout_minutes`` will be falsely classified as stale.
        That triggers duplicate processing — the sweep recovers the row,
        another pod claims and re-runs it, while the original pod is
        still working toward its commit.  Mitigation today: set
        ``STALE_JOB_TIMEOUT_MINUTES`` *above* the longest plausible job
        runtime (default 60 min, raise if needed).  Plan 310C wires a
        per-job heartbeat into the generic ``run_job`` runner; until
        then, this method shares the same long-running-job hazard as the
        manual ``recover_job`` path — the sweep just exercises it more
        often.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_timeout_minutes)
        stale_filter = and_(
            col(DataIngestionJob.state) == IngestionState.RUNNING,
            or_(
                col(DataIngestionJob.locked_at).is_(None),
                col(DataIngestionJob.locked_at) < cutoff,
            ),
        )

        # Bucket 1: still has retries left → unlock and let claim_job pick
        # it up next cycle.  Preserve ``attempts`` so claim_job's
        # ``attempts < max_attempts`` guard caps the retry count.
        recovered = await self.session.execute(
            update(DataIngestionJob)
            .where(
                stale_filter,
                col(DataIngestionJob.attempts) < col(DataIngestionJob.max_attempts),
            )
            .values(
                state=IngestionState.NOT_STARTED,
                locked_by=None,
                locked_at=None,
                is_current=False,
                run_after=None,
            )
            .returning(col(DataIngestionJob.id))
        )
        recovered_ids = list(recovered.scalars().all())

        # Bucket 2: out of retries → mark FINISHED+ERROR loud and clear.
        abandoned = await self.session.execute(
            update(DataIngestionJob)
            .where(
                stale_filter,
                col(DataIngestionJob.attempts) >= col(DataIngestionJob.max_attempts),
            )
            .values(
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                # Terminal transition — stamp finished_at so the dashboard
                # query sees auto-abandoned rows alongside normal completions.
                finished_at=func.now(),
                status_message=(
                    "Auto-recovery: pod-crash sweep found this job RUNNING past "
                    "the stale-timeout window with attempts >= max_attempts.  "
                    "Marking FINISHED+ERROR.  If the underlying issue is fixed, "
                    "create a new job — this row's attempts counter is exhausted."
                ),
            )
            .returning(col(DataIngestionJob.id))
        )
        abandoned_ids = list(abandoned.scalars().all())

        await self.session.commit()
        return len(recovered_ids), len(abandoned_ids)

    async def recover_job(
        self, job_id: int, stale_timeout_minutes: int
    ) -> Optional[DataIngestionJob]:
        """Reset a job stuck in RUNNING (pod crash) back to NOT_STARTED.

        Atomic UPDATE — safe under concurrent claim/recover.  Only succeeds
        when locked_at is older than ``stale_timeout_minutes`` (or NULL).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_timeout_minutes)
        result = await self.session.execute(
            update(DataIngestionJob)
            .where(
                col(DataIngestionJob.id) == job_id,
                col(DataIngestionJob.state) == IngestionState.RUNNING,
                or_(
                    col(DataIngestionJob.locked_at).is_(None),
                    col(DataIngestionJob.locked_at) < cutoff,
                ),
            )
            .values(
                state=IngestionState.NOT_STARTED,
                locked_by=None,
                locked_at=None,
                is_current=False,
                attempts=0,
                run_after=None,
            )
            .returning(col(DataIngestionJob.id))
        )
        await self.session.commit()
        recovered_id = result.scalar_one_or_none()
        if recovered_id is None:
            return None
        return await self.get_job_by_id(recovered_id)

    def _pending_jobs_query(self, limit: int = 10):
        """Build the query used by the safety poller.

        Uses FOR UPDATE SKIP LOCKED to let multiple pods pick up different jobs.
        """
        return (
            select(DataIngestionJob)
            .where(
                col(DataIngestionJob.state) == IngestionState.NOT_STARTED,
                or_(
                    col(DataIngestionJob.run_after).is_(None),
                    col(DataIngestionJob.run_after) <= func.now(),
                ),
                col(DataIngestionJob.locked_by).is_(None),
                col(DataIngestionJob.attempts) < col(DataIngestionJob.max_attempts),
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )

    async def get_latest_jobs_by_year(self, year: int) -> List[DataIngestionJob]:
        """
        Get the current job for each (module_type_id, target_type) combination.

        Args:
            year: The year to filter jobs by

        Returns:
            List of DataIngestionJob objects where is_current = true
        """
        # // maybe we can optimize, by not giving the meta field ?
        stmt = (
            select(DataIngestionJob)
            .where(
                DataIngestionJob.year == year,
                DataIngestionJob.is_current,
            )
            .order_by(
                col(DataIngestionJob.module_type_id), col(DataIngestionJob.target_type)
            )
        )
        exec_result = await self.session.execute(stmt)
        return list(exec_result.scalars().all())

    async def mark_job_as_current(self, job: DataIngestionJob) -> None:
        """
        Mark a job as current, unsetting any previous current job.

        This must be called within a transaction to ensure atomicity.
        # TODO: change that. jobs that have started processing can be marked as current,
        # even if they are not finished yet. Goal is to allow the frontend to show the
        # latest job as current, even if it's still processing, instead of showing the
        # previous finished job as current until the new one is finished.
        Only FINISHED AND RUNNING jobs can be marked as current.

        Args:
            job: The DataIngestionJob to mark as current
        """
        if job.state not in (IngestionState.RUNNING, IngestionState.FINISHED):
            logger.warning(
                f"Job {job.id} state {job.state} not eligible for is_current"
            )
            return

        if job.target_type is None:
            raise ValueError("target_type cannot be None when marking job as current")

        try:
            # Mirror claim_job's invariant: never demote a RUNNING sibling,
            # since that would let two pods process the same combo
            # concurrently (the partial unique index can't catch it once
            # the demote commits).
            where_clause = and_(
                col(DataIngestionJob.is_current),
                col(DataIngestionJob.state) != IngestionState.RUNNING,
                col(DataIngestionJob.module_type_id) == job.module_type_id,
                col(DataIngestionJob.target_type) == job.target_type,
                col(DataIngestionJob.year) == job.year,
                col(DataIngestionJob.ingestion_method) == job.ingestion_method,
            )

            if job.data_entry_type_id is not None:
                where_clause = and_(
                    where_clause,
                    col(DataIngestionJob.data_entry_type_id) == job.data_entry_type_id,
                )
            else:
                # NULL != NULL in SQL — must use IS NULL explicitly
                where_clause = and_(
                    where_clause,
                    col(DataIngestionJob.data_entry_type_id).is_(None),
                )

            logger.info(f"Unsetting is_current for: {where_clause}")

            # Unset previous current job for this combination
            unset_stmt = (
                update(DataIngestionJob).where(where_clause).values(is_current=False)
            )
            result = await self.session.execute(unset_stmt)
            if result is not None and hasattr(result, "rowcount"):
                logger.info(
                    f"Unset is_current for {result.rowcount} job(s) matching criteria"
                )
            # Set new current job
            job.is_current = True
            await self.session.flush()
            logger.info(f"Job {job.id} marked as current")

        except Exception as e:
            logger.error(f"Failed to mark job {job.id} as current: {e}")
            raise

    async def cancel_job(self, job_id: int) -> Optional[DataIngestionJob]:
        """
        Cancel a stuck job by setting it to FINISHED/ERROR and unsetting is_current.

        Only jobs in NOT_STARTED, QUEUED, or RUNNING state can be cancelled.

        Args:
            job_id: The ID of the job to cancel

        Returns:
            The updated job, or None if not found or not cancellable
        """
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        exec_result = await self.session.execute(stmt)
        job = exec_result.scalar_one_or_none()
        if not job:
            return None

        if job.state not in (
            IngestionState.NOT_STARTED,
            IngestionState.QUEUED,
            IngestionState.RUNNING,
        ):
            logger.warning(f"Job {job_id} state {job.state} not cancellable")
            return None

        job.state = IngestionState.FINISHED
        job.result = IngestionResult.ERROR
        job.status_message = "Cancelled by user"
        # Terminal transition — stamp finished_at so observability queries
        # see cancelled rows alongside success/error completions.
        if job.finished_at is None:
            job.finished_at = func.now()
        job.is_current = False
        merged_meta = {
            **self.sanitize_for_json(job.meta or {}),
            "cancelled": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        job.meta = merged_meta
        await self.session.flush()
        await self.session.refresh(job)
        logger.info(f"Job {job_id} cancelled")
        return job

    async def _get_jobs_by_state(
        self, states: list[IngestionState], negate: bool = False
    ) -> list[DataIngestionJob]:
        """
        Helper method to fetch jobs filtered by state.

        Args:
            states: List of IngestionState values to filter by
            negate: If True, exclude jobs with these states (use notin_)

        Returns:
            List of DataIngestionJob objects ordered by id descending
        """
        state_filter = (
            col(DataIngestionJob.state).notin_(states)
            if negate
            else col(DataIngestionJob.state).in_(states)
        )
        stmt = (
            select(DataIngestionJob)
            .where(state_filter)
            .order_by(desc(DataIngestionJob.id))
        )
        exec_result = await self.session.execute(stmt)
        return list(exec_result.scalars().all())

    async def get_finished_jobs(self) -> list[DataIngestionJob]:
        """
        Get all jobs that are in a finished state.
        """
        return await self._get_jobs_by_state([IngestionState.FINISHED])

    async def get_active_jobs(self) -> list[DataIngestionJob]:
        """
        Get all jobs that are not in a finished state.
        Used for SSE streaming of job updates.
        """
        return await self._get_jobs_by_state([IngestionState.FINISHED], negate=True)

    async def get_recalculation_status_by_year(
        self, year: int
    ) -> list["RecalculationStatusRow"]:
        """Derive per-(module_type_id, data_entry_type_id) recalculation status.

        For each combination, compares the latest is_current FACTORS job ID
        against the is_current DATA_ENTRIES/computed job ID.
        ``needs_recalculation`` is True when no recalculation job exists yet, or
        the last factor sync is more recent (higher serial PK) than the last
        recalculation.

        Args:
            year: The report year to scope the query.

        Returns:
            List of RecalculationStatusRow dicts, one per
            (module_type_id, data_entry_type_id) that has at least one
            qualifying FACTORS job.
        """
        # Sub-query: latest is_current FACTORS job per
        # (module_type_id, data_entry_type_id)
        # Excludes ERROR results so a failed factor sync never triggers recalculation.
        factor_jobs_sub = (
            select(
                col(DataIngestionJob.module_type_id).label("module_type_id"),
                col(DataIngestionJob.data_entry_type_id).label("data_entry_type_id"),
                func.max(col(DataIngestionJob.id)).label("max_factor_job_id"),
            )
            .where(
                col(DataIngestionJob.is_current).is_(True),
                col(DataIngestionJob.year) == year,
                col(DataIngestionJob.state) == IngestionState.FINISHED,
                col(DataIngestionJob.target_type) == TargetType.FACTORS,
                col(DataIngestionJob.result) != IngestionResult.ERROR,
                col(DataIngestionJob.data_entry_type_id).isnot(None),
            )
            .group_by(
                col(DataIngestionJob.module_type_id),
                col(DataIngestionJob.data_entry_type_id),
            )
            .subquery()
        )

        # Sub-query: is_current DATA_ENTRIES/computed job per
        # (module_type_id, data_entry_type_id)
        recalc_jobs_sub = (
            select(
                col(DataIngestionJob.module_type_id).label("module_type_id"),
                col(DataIngestionJob.data_entry_type_id).label("data_entry_type_id"),
                col(DataIngestionJob.id).label("recalc_job_id"),
                col(DataIngestionJob.result).label("recalc_job_result"),
            )
            .where(
                col(DataIngestionJob.is_current).is_(True),
                col(DataIngestionJob.year) == year,
                col(DataIngestionJob.target_type) == TargetType.DATA_ENTRIES,
                col(DataIngestionJob.ingestion_method) == IngestionMethod.computed,
                col(DataIngestionJob.data_entry_type_id).isnot(None),
            )
            .subquery()
        )

        # LEFT JOIN: factor combos left-join recalculation combos
        # SQLAlchemy stubs only define up to 4 positional args for select()
        stmt = select(  # type: ignore[call-overload]
            factor_jobs_sub.c.module_type_id,
            factor_jobs_sub.c.data_entry_type_id,
            factor_jobs_sub.c.max_factor_job_id,
            recalc_jobs_sub.c.recalc_job_id,
            recalc_jobs_sub.c.recalc_job_result,
        ).join(
            recalc_jobs_sub,
            and_(
                factor_jobs_sub.c.module_type_id == recalc_jobs_sub.c.module_type_id,
                factor_jobs_sub.c.data_entry_type_id
                == recalc_jobs_sub.c.data_entry_type_id,
            ),
            isouter=True,
        )

        exec_result = await self.session.execute(stmt)
        rows = exec_result.all()

        # Fetch only id + result for factor jobs — avoids loading the meta JSON field.
        factor_job_ids = [r.max_factor_job_id for r in rows]
        factor_job_result_by_id: dict[int, Optional[IngestionResult]] = {}
        if factor_job_ids:
            fj_stmt = select(
                col(DataIngestionJob.id),
                col(DataIngestionJob.result),
            ).where(col(DataIngestionJob.id).in_(factor_job_ids))
            fj_result = await self.session.execute(fj_stmt)
            for fj_row in fj_result.all():
                if fj_row.id is not None:
                    factor_job_result_by_id[fj_row.id] = fj_row.result

        status_rows: list[RecalculationStatusRow] = []
        for row in rows:
            needs_recalculation = (
                row.recalc_job_id is None
                or row.max_factor_job_id > row.recalc_job_id
                or row.recalc_job_result == IngestionResult.ERROR
            )
            status_rows.append(
                RecalculationStatusRow(
                    module_type_id=row.module_type_id,
                    data_entry_type_id=row.data_entry_type_id,
                    year=year,
                    needs_recalculation=needs_recalculation,
                    last_factor_job_id=row.max_factor_job_id,
                    last_factor_job_result=factor_job_result_by_id.get(
                        row.max_factor_job_id
                    ),
                    last_recalculation_job_id=row.recalc_job_id,
                    last_recalculation_job_result=row.recalc_job_result,
                )
            )
        return status_rows


class RecalculationStatusRow(TypedDict):
    """Lightweight status row returned by get_recalculation_status_by_year."""

    module_type_id: int
    data_entry_type_id: int
    year: int
    needs_recalculation: bool
    last_factor_job_id: Optional[int]
    last_factor_job_result: Optional[IngestionResult]
    last_recalculation_job_id: Optional[int]
    last_recalculation_job_result: Optional[IngestionResult]
