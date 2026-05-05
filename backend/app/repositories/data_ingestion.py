import enum
from datetime import datetime, timedelta, timezone
from typing import List, Optional, TypedDict

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
        """Update ingestion job with legacy status_code and new state/result.

        Args:
            job_id: Job ID to update
            status_message: Status message
            status_code: Legacy status code (for backward compatibility)
            metadata: Metadata to merge
            completed_at: Optional completed timestamp
            state: New state value (optional, for new code)
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
