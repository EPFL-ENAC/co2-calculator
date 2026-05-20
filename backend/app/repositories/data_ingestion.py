import enum
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional, TypedDict
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, desc, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    Pipeline,
    PipelineStatus,
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
            # #1236 #2A — generic status_history timeline: append every
            # status_message update (with timestamp) to a bounded list
            # so the ops console can show "what happened, when" for
            # every job_type — not just the latest status_message that
            # this same UPDATE overwrites above. Bounded to keep meta
            # payloads tractable on long-lived / retried jobs.
            history = list(merged_meta.get("status_history") or [])
            if status_message:
                history.append(
                    {
                        "message": status_message,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                )
                # Cap to last N to bound the meta payload. 50 covers
                # the busiest job (multi-phase unit_sync, retries) with
                # margin; trim from the head when exceeded.
                if len(history) > 50:
                    history = history[-50:]
                merged_meta["status_history"] = history
            result_job.meta = merged_meta
            await self.session.flush()
            await self.session.refresh(result_job)
        return result_job

    async def finish_job(
        self,
        job_id: int,
        pod_id: str,
        result: IngestionResult,
        status_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Atomic compare-and-set transition to ``FINISHED`` for the owning pod.

        Plan 310 review finding **B-C1** — the prior ``update_ingestion_job``
        FINISHED path did a ``SELECT … WHERE id`` then mutated state without
        a CAS guard, so a pod whose heartbeat failed during a DB outage could
        complete its handler AFTER another pod recovered the row and
        re-claimed it; its FINISHED write then clobbered the new owner's
        RUNNING state.

        This method enforces the missing CAS:

            UPDATE data_ingestion_jobs
            SET state=FINISHED, result=:result, finished_at=…, meta=…, …
            WHERE id=:job_id AND locked_by=:pod_id AND state=RUNNING
            RETURNING id

        Returns:
            True  — the row was ours and we wrote FINISHED (rowcount==1).
            False — we were preempted between handler completion and this
                    write (rowcount==0).  The caller must NOT retry, must
                    NOT re-raise, and must let the new owner close the row.

        Atomicity:
            ``locked_by == pod_id AND state == RUNNING`` makes meta-merge
            safe: only the lock owner can write meta while it holds the
            lock, so SELECT-then-merge-then-UPDATE-with-CAS has no TOCTOU
            window for the same row.

        Idempotent ``finished_at`` (Plan 310-C observability): use
            ``coalesce(finished_at, now())`` — matches the ``started_at``
            pattern in ``claim_job`` (the CAS UPDATE has no Python read step
            we could guard with an ``IS NULL`` check, so the coalesce keeps
            an already-stamped timestamp intact).

        Optional kwargs (``status_message``, ``metadata``) match the
        ``update_ingestion_job`` shape so the runner can swap call sites
        without losing fields.  When omitted, those columns are not
        touched (we don't NULL them out).
        """
        # Pre-read meta so we can merge with any new metadata.  Safe under
        # the WHERE-CAS: if we're preempted between this read and the
        # UPDATE, the UPDATE matches no row, the merged dict is dropped,
        # and the new owner's eventual finish_job writes its own meta.
        values: dict = {
            "state": IngestionState.FINISHED,
            "result": result,
            "finished_at": func.coalesce(col(DataIngestionJob.finished_at), func.now()),
        }
        if status_message is not None:
            values["status_message"] = status_message

        if metadata is not None:
            existing = await self.session.execute(
                select(DataIngestionJob.meta).where(
                    col(DataIngestionJob.id) == job_id,
                    col(DataIngestionJob.locked_by) == pod_id,
                    col(DataIngestionJob.state) == IngestionState.RUNNING,
                )
            )
            existing_meta = existing.scalar_one_or_none() or {}
            merged_meta = {
                **self.sanitize_for_json(existing_meta),
                **self.sanitize_for_json(metadata),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            values["meta"] = merged_meta

        result_obj = await self.session.execute(
            update(DataIngestionJob)
            .where(
                col(DataIngestionJob.id) == job_id,
                col(DataIngestionJob.locked_by) == pod_id,
                col(DataIngestionJob.state) == IngestionState.RUNNING,
            )
            .values(**values)
            .returning(col(DataIngestionJob.id))
        )
        updated_id = result_obj.scalar_one_or_none()
        await self.session.commit()
        return updated_id is not None

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

    async def list_pipelines_paginated(
        self,
        *,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
        job_type: Optional[str] = None,
        module_type_id: Optional[int] = None,
        year: Optional[int] = None,
        has_errors: Optional[bool] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        q: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list["PipelineGroup"], int]:
        """Paginated, filtered list of pipelines for the ops console (#1234).

        The pagination unit is the *pipeline* (one ``pipeline_id`` = a
        parent + its fan-out children), never the job row — children
        must not split across pages.  A pipeline qualifies when it has
        at least one row matching the row-level filters; ``has_errors``
        is evaluated at the pipeline level (any FINISHED+ERROR job).

        Rows with ``pipeline_id IS NULL`` (a parent that failed before
        fan-out, so it never minted a pipeline) surface as synthetic
        *pipelines-of-one* so operators still see them.

        Grouping is done in SQL with ``GROUP BY`` + ``MAX(id)`` (no
        ``DISTINCT ON`` — not portable to the SQLite unit-test fixture),
        then the per-page rows are fetched in one ``IN`` query and
        grouped in Python.  Matches the in-memory-pick precedent of
        ``get_current_pipeline_ids_for_modules`` (realistic input size:
        a few thousand pipelines at most).

        Returns ``(groups, total)`` where ``groups`` is the requested
        page ordered newest-first by latest job id and ``total`` is the
        full match count for pagination.
        """
        conds = []
        if state is not None:
            conds.append(col(DataIngestionJob.state) == state)
        if result is not None:
            conds.append(col(DataIngestionJob.result) == result)
        if job_type is not None:
            conds.append(col(DataIngestionJob.job_type) == job_type)
        if module_type_id is not None:
            conds.append(col(DataIngestionJob.module_type_id) == module_type_id)
        if year is not None:
            conds.append(col(DataIngestionJob.year) == year)
        if since is not None:
            conds.append(col(DataIngestionJob.started_at) >= since)
        if until is not None:
            conds.append(col(DataIngestionJob.started_at) <= until)
        if q:
            conds.append(col(DataIngestionJob.status_message).ilike(f"%{q}%"))

        # Pipeline-level error set (FINISHED+ERROR anywhere in the
        # group) — only computed when the caller filters on it.
        error_pids: set[UUID] = set()
        if has_errors is not None:
            err_stmt = (
                select(DataIngestionJob.pipeline_id)
                .where(
                    col(DataIngestionJob.pipeline_id).isnot(None),
                    col(DataIngestionJob.state) == IngestionState.FINISHED,
                    col(DataIngestionJob.result) == IngestionResult.ERROR,
                )
                .distinct()
            )
            error_pids = {r[0] for r in (await self.session.execute(err_stmt)).all()}

        # Grouped pipelines: (pipeline_id, latest job id).
        grouped_stmt = (
            select(
                DataIngestionJob.pipeline_id,
                func.max(col(DataIngestionJob.id)).label("latest_id"),
            )
            .where(col(DataIngestionJob.pipeline_id).isnot(None), *conds)
            .group_by(col(DataIngestionJob.pipeline_id))
        )
        grouped = (await self.session.execute(grouped_stmt)).all()

        # Orphans: each NULL-pipeline row is its own pipeline-of-one.
        orphan_conds = list(conds)
        if has_errors is True:
            orphan_conds += [
                col(DataIngestionJob.state) == IngestionState.FINISHED,
                col(DataIngestionJob.result) == IngestionResult.ERROR,
            ]
        elif has_errors is False:
            orphan_conds.append(
                or_(
                    col(DataIngestionJob.state) != IngestionState.FINISHED,
                    col(DataIngestionJob.result) != IngestionResult.ERROR,
                    col(DataIngestionJob.result).is_(None),
                )
            )
        orphan_stmt = select(col(DataIngestionJob.id)).where(
            col(DataIngestionJob.pipeline_id).is_(None), *orphan_conds
        )
        orphan_ids = [r[0] for r in (await self.session.execute(orphan_stmt)).all()]

        # Merge + order newest-first by latest id, then paginate.
        merged: list[tuple[int, Optional[UUID], int]] = []
        for pid, latest_id in grouped:
            if has_errors is True and pid not in error_pids:
                continue
            if has_errors is False and pid in error_pids:
                continue
            merged.append((latest_id, pid, latest_id))
        for oid in orphan_ids:
            merged.append((oid, None, oid))
        merged.sort(key=lambda t: t[0], reverse=True)
        total = len(merged)
        page = merged[offset : offset + limit]

        page_pids = [pid for _, pid, _ in page if pid is not None]
        page_orphan_ids = [k for _, pid, k in page if pid is None]

        by_pid: dict[UUID, list[DataIngestionJob]] = {}
        if page_pids:
            jstmt = (
                select(DataIngestionJob)
                .where(col(DataIngestionJob.pipeline_id).in_(page_pids))
                .order_by(col(DataIngestionJob.id).asc())
            )
            for job in (await self.session.execute(jstmt)).scalars().all():
                by_pid.setdefault(job.pipeline_id, []).append(job)

        by_orphan: dict[int, DataIngestionJob] = {}
        if page_orphan_ids:
            ostmt = select(DataIngestionJob).where(
                col(DataIngestionJob.id).in_(page_orphan_ids)
            )
            for job in (await self.session.execute(ostmt)).scalars().all():
                by_orphan[job.id] = job

        groups: list[PipelineGroup] = []
        for _, pid, key in page:
            if pid is not None:
                groups.append(
                    PipelineGroup(
                        pipeline_id=pid,
                        is_orphan=False,
                        jobs=by_pid.get(pid, []),
                    )
                )
            else:
                job = by_orphan.get(key)
                groups.append(
                    PipelineGroup(
                        pipeline_id=None,
                        is_orphan=True,
                        jobs=[job] if job is not None else [],
                    )
                )
        return groups, total

    async def ensure_pipeline_exists(
        self,
        pipeline_id: UUID,
        *,
        kind: Optional[str] = None,
        entity_type: Optional[int] = None,
        ingestion_method: Optional[int] = None,
        module_type_id: Optional[int] = None,
        year: Optional[int] = None,
    ) -> None:
        """Idempotently create the `pipelines` row (#1236 Phase 1).

        Called from the parent-creation mint sites (not the runner —
        the runner is a terminal actor). Fast-path SELECT skips the
        common already-exists case; the SAVEPOINT around the INSERT
        contains a concurrent-creator ``IntegrityError`` so it never
        poisons the caller's transaction (the #1225 discipline; mirrors
        ``claim_job``'s ``begin_nested`` use here).
        """
        existing = await self.session.execute(
            select(Pipeline.id).where(col(Pipeline.id) == pipeline_id)
        )
        if existing.first() is not None:
            return
        try:
            async with self.session.begin_nested():
                self.session.add(
                    Pipeline(
                        id=pipeline_id,
                        kind=kind,
                        entity_type=entity_type,
                        ingestion_method=ingestion_method,
                        module_type_id=module_type_id,
                        year=year,
                        status=PipelineStatus.NOT_STARTED.value,
                    )
                )
                await self.session.flush()
        except IntegrityError:
            # A concurrent creator won the race — idempotent no-op.
            pass

    async def recompute_pipeline_status(self, pipeline_id: UUID) -> Optional[str]:
        """Recompute-and-store the pipeline's authoritative status (#1236).

        The single source of truth is the pure
        ``compute_pipeline_progress`` over the pipeline's jobs — never
        an incremental accumulator (drift = the #1219 bug class).

        Option (a) — last-child oracle: only writes when
        ``progress.done`` (the terminal that flips it is, by
        definition, the last expected child); a non-terminal call is a
        cheap read + skip. Self-healing: a skipped/lost write is
        recovered by the next terminal or the reconciliation sweep.

        Does NOT commit — the caller owns the transaction boundary
        (the runner wraps this in its post-``finish_job`` isolated
        try/except; the sweep batches). Returns the written status, or
        ``None`` when skipped (no jobs / not done).
        """
        # Local import: pure function, models-only deps; avoids a
        # module-level service→repo edge.
        from app.services.pipeline_progress import compute_pipeline_progress

        jobs = await self.list_jobs_by_pipeline_id(pipeline_id)
        if not jobs:
            return None
        progress = compute_pipeline_progress(jobs)
        if not progress["done"]:
            return None  # not the last child — skip (option a)

        errored = [
            j
            for j in jobs
            if j.state == IngestionState.FINISHED and j.result == IngestionResult.ERROR
        ]
        # Phase-1 mapping. PARTIAL is reserved (model enum) but not
        # emitted until the FAILED-vs-PARTIAL boundary open question is
        # decided — do not invent a definition here.
        new_status = (
            PipelineStatus.FAILED.value if errored else PipelineStatus.SUCCESS.value
        )
        # ``last_error`` must carry signal, not the #1219 lie: a
        # ``csv_ingest`` that succeeded then poisoned downstream has
        # ``result=ERROR`` but ``status_message="Success"`` (jobs
        # 2/47/49/74 shape). Prefer an errored job whose message is
        # NOT "Success"; fall back to the first errored only if every
        # one is uninformative. (Phase 2 backfill reuses this logic
        # across all history — must not write "last_error: Success".)
        last_error: Optional[str] = None
        if errored:
            informative = [
                j
                for j in errored
                if (j.status_message or "").strip().lower() != "success"
            ]
            last_error = (informative or errored)[0].status_message
        started = [j.started_at for j in jobs if j.started_at is not None]
        finished = [j.finished_at for j in jobs if j.finished_at is not None]
        await self.session.execute(
            update(Pipeline)
            .where(col(Pipeline.id) == pipeline_id)
            .values(
                status=new_status,
                job_count=len(jobs),
                error_count=len(errored),
                started_at=min(started) if started else None,
                finished_at=max(finished) if finished else None,
                last_error=last_error,
                updated_at=func.now(),
            )
        )
        return new_status

    async def reconcile_pipeline_statuses(self) -> dict:
        """Phase-1 standalone reconciliation sweep (#1236).

        The durable backstop for the runner's isolated post-finish
        write: that write log-and-skips on any DB error, so status can
        lag. This recomputes-and-stores every pipeline that has jobs
        (idempotent; commits per pipeline so a mid-sweep failure keeps
        prior fixes). Phase 3 schedules this on a cron before flipping
        reads; Phase 1 just ships it callable.

        Returns ``{"checked": n, "corrected": m}``.
        """
        pid_rows = await self.session.execute(
            select(col(DataIngestionJob.pipeline_id))
            .where(col(DataIngestionJob.pipeline_id).isnot(None))
            .distinct()
        )
        pids = [r[0] for r in pid_rows.all()]
        checked = 0
        corrected = 0
        for pid in pids:
            checked += 1
            before = (
                await self.session.execute(
                    select(col(Pipeline.status)).where(col(Pipeline.id) == pid)
                )
            ).scalar_one_or_none()
            after = await self.recompute_pipeline_status(pid)
            await self.session.commit()
            if after is not None and after != before:
                corrected += 1
        return {"checked": checked, "corrected": corrected}

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

    async def get_current_pipeline_ids_for_modules(
        self,
        module_type_ids: List[int],
        year: int,
    ) -> dict[int, UUID]:
        """Bulk-fetch sibling of ``get_current_pipeline_id_for_module``.

        Plan 310-D — backs ``CarbonReportModuleService.list_modules``
        which previously did one query per module (an N+1 on a
        frontend-facing endpoint).  A typical carbon report has ~10
        modules → this collapses 10 round-trips into one.

        Returns ``{module_type_id: pipeline_id}`` for every module
        in ``module_type_ids`` that has at least one active
        (NOT_STARTED/QUEUED/RUNNING) pipeline-attached job for the
        given ``year``.  Modules without an active pipeline are
        absent from the dict — callers use ``.get(...)`` and treat
        missing keys as "no badge".

        Implementation: single ``WHERE module_type_id IN (...) AND
        year = :year AND ...`` query returns every active pipeline
        row for the requested modules; per-module "most recent"
        picking happens in Python.  ``DISTINCT ON (module_type_id)``
        would let PG do it server-side but isn't portable to the
        SQLite-backed unit-test fixture, and at the realistic input
        size (≤20 modules × ≤few active rows each) the in-memory
        pick is free.

        Empty input → empty dict (no query fired).
        """
        if not module_type_ids:
            return {}

        stmt = (
            select(
                DataIngestionJob.module_type_id,
                DataIngestionJob.pipeline_id,
                DataIngestionJob.id,
            )
            .where(
                col(DataIngestionJob.module_type_id).in_(module_type_ids),
                col(DataIngestionJob.year) == year,
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
        )
        exec_result = await self.session.execute(stmt)

        # The ORDER BY id DESC means the first row we see for a given
        # module_type_id is the most recent — keep it, ignore later
        # (older) entries.  ``setdefault`` on a dict gives us that
        # "first wins" semantics in one pass.
        picked: dict[int, UUID] = {}
        for row in exec_result.all():
            module_id, pipeline_id, _job_id = row
            if module_id is None or pipeline_id is None:
                continue
            picked.setdefault(module_id, pipeline_id)
        return picked

    async def get_active_year_level_pipeline_ids(self, year: int) -> list[UUID]:
        """Return active ``GLOBAL_PER_YEAR`` pipeline_ids for the given year.

        Plan 310-D / Issue #867 — sibling of ``get_current_pipeline_ids_for_modules``
        for **year-level** pipelines (e.g. the unit-sync chain minted by
        the back-office "create year" flow).  These are not module-scoped
        so the existing module-keyed helper can't see them; the SSE
        watcher on ``DataManagementPage.vue`` reload-rehydrate path needs
        to enumerate them on its own.

        "Active" mirrors the module-scoped sibling: any non-terminal
        state (``NOT_STARTED`` / ``QUEUED`` / ``RUNNING``).  The
        ``pipeline_id IS NOT NULL`` guard is what keeps the result
        empty when the pipeline-stamping side of the unit-sync flow
        hasn't shipped yet — legacy unit_sync jobs stay invisible
        (no SSE stream to attach to anyway), and the watcher idles.

        We dedupe in Python rather than ``DISTINCT`` server-side so
        the SQLite-backed unit-test fixture works the same as PG (the
        pattern used by the module sibling) and the result is ordered
        most-recent-first by job id for deterministic test output.
        """
        stmt = (
            select(DataIngestionJob.pipeline_id, DataIngestionJob.id)
            .where(
                col(DataIngestionJob.entity_type) == EntityType.GLOBAL_PER_YEAR,
                col(DataIngestionJob.year) == year,
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
        )
        exec_result = await self.session.execute(stmt)

        # Multiple jobs can share one pipeline_id (parent + fan-out
        # children — same pattern as module pipelines).  Dedupe while
        # preserving the id-DESC traversal order so the first
        # occurrence (most recent job) wins.
        seen: set[UUID] = set()
        ordered: list[UUID] = []
        for row in exec_result.all():
            pipeline_id, _job_id = row
            if pipeline_id is None:
                continue
            if pipeline_id in seen:
                continue
            seen.add(pipeline_id)
            ordered.append(pipeline_id)
        return ordered

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
            # Expected non-claim outcome (locked, attempts exhausted,
            # run_after in the future, …).  Debug-level so the polling
            # loop doesn't flood production logs but operators can still
            # opt in when triaging "why didn't this job get picked up".
            logger.debug(
                "claim_job: job_id=%s not claimable (locked/attempts/run_after)",
                job_id,
            )
            return False
        except IntegrityError:
            # Step 2 tripped the partial unique index
            # ``ix_data_ingestion_jobs_is_current_unique`` — another pod
            # already flipped a sibling for the same combo to
            # is_current=TRUE.  Expected on rare two-pod races; if it
            # repeats for the same job_id the row is permanently stuck
            # and operators need visibility.  WARN with exc_info so
            # log aggregation surfaces the IntegrityError detail.
            logger.warning(
                "claim_job IntegrityError on job_id=%s",
                job_id,
                exc_info=True,
            )
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

    async def find_stale_aggregations(
        self, threshold_minutes: int
    ) -> list["StaleStatsRow"]:
        """Return one row per ``(module_type_id, year)`` whose aggregation is
        stale or missing.

        Plan 310-D Follow-up 1 (#1063) — backstop for passive monitoring of
        the aggregation pipeline.  The runner-driven chain surfaces failures
        interactively (badge + logs); this query catches the cases nobody is
        watching: stuck NOT_STARTED rows, last-run errors, slow-burn drift.

        Source-of-truth for "what should have an aggregation" is
        ``carbon_report_modules`` × ``carbon_reports.year`` (the modules
        themselves declare their own scope).  We LEFT JOIN to the latest
        ``job_type='aggregation'`` row per scope (``MAX(id)`` — within a
        scope, id ordering tracks chronological insertion since serial PKs
        are monotonically allocated).

        Classification (``why_stale``):

        - ``no_aggregation_ever`` — module exists but no aggregation row
          was ever inserted for that ``(module_type_id, year)``.
        - ``pending_aggregation_stuck`` — latest row is in a non-terminal
          state (NOT_STARTED / QUEUED / RUNNING).  The stuck-state runner
          sweeper handles RUNNING leases separately, but a NOT_STARTED row
          that never got picked up surfaces here.
        - ``last_aggregation_failed`` — latest row is FINISHED with
          ``result=ERROR``.
        - ``last_aggregation_too_old`` — latest row is FINISHED with
          ``result != ERROR`` but ``finished_at`` is older than the cutoff
          (or NULL).

        Successful, fresh aggregations (FINISHED, non-ERROR, finished_at
        within the window) are filtered out — they aren't stale.

        Args:
            threshold_minutes: How long since ``finished_at`` qualifies as
                "too old".  Caller is responsible for range-checking
                (``>= 1``).

        Returns:
            Unsorted list of stale entries.  The endpoint stamps the HTTP
            response shape; the repo stays Pydantic-free.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)

        # Latest aggregation row per (module_type_id, year), regardless of
        # state — pending rows must be visible alongside finished ones.
        latest_agg_sub = (
            select(
                col(DataIngestionJob.module_type_id).label("module_type_id"),
                col(DataIngestionJob.year).label("year"),
                func.max(col(DataIngestionJob.id)).label("latest_job_id"),
            )
            .where(
                col(DataIngestionJob.job_type) == "aggregation",
                col(DataIngestionJob.module_type_id).isnot(None),
                col(DataIngestionJob.year).isnot(None),
            )
            .group_by(
                col(DataIngestionJob.module_type_id),
                col(DataIngestionJob.year),
            )
            .subquery()
        )

        # Seed: distinct (module_type_id, carbon_reports.year) the modules
        # themselves declare.  DISTINCT keeps the seed one row per scope
        # even when many units share the same (module_type_id, year).
        scopes_sub = (
            select(
                col(CarbonReportModule.module_type_id).label("module_type_id"),
                col(CarbonReport.year).label("year"),
            )
            .join(
                CarbonReport,
                col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
            )
            .distinct()
            .subquery()
        )

        # LEFT JOIN scopes → latest aggregation; rows with NULL latest_job_id
        # are the "no_aggregation_ever" bucket.
        stmt = select(
            scopes_sub.c.module_type_id,
            scopes_sub.c.year,
            latest_agg_sub.c.latest_job_id,
        ).join(
            latest_agg_sub,
            and_(
                scopes_sub.c.module_type_id == latest_agg_sub.c.module_type_id,
                scopes_sub.c.year == latest_agg_sub.c.year,
            ),
            isouter=True,
        )
        scope_rows = (await self.session.execute(stmt)).all()

        # Hydrate the latest job rows in one extra round-trip — only the
        # state/result/finished_at columns are needed for classification.
        latest_ids = [
            r.latest_job_id for r in scope_rows if r.latest_job_id is not None
        ]
        latest_jobs: dict[int, DataIngestionJob] = {}
        if latest_ids:
            jobs_stmt = select(DataIngestionJob).where(
                col(DataIngestionJob.id).in_(latest_ids)
            )
            jobs_result = await self.session.execute(jobs_stmt)
            for job in jobs_result.scalars().all():
                if job.id is not None:
                    latest_jobs[job.id] = job

        out: list[StaleStatsRow] = []
        for r in scope_rows:
            job = (
                latest_jobs.get(r.latest_job_id)
                if r.latest_job_id is not None
                else None
            )
            if job is None:
                out.append(
                    StaleStatsRow(
                        module_type_id=r.module_type_id,
                        year=r.year,
                        last_finished_aggregation_at=None,
                        why_stale="no_aggregation_ever",
                        last_aggregation_job_id=None,
                    )
                )
                continue

            if job.state != IngestionState.FINISHED:
                # NOT_STARTED / QUEUED / RUNNING — runner hasn't terminally
                # resolved this row yet.
                out.append(
                    StaleStatsRow(
                        module_type_id=r.module_type_id,
                        year=r.year,
                        last_finished_aggregation_at=None,
                        why_stale="pending_aggregation_stuck",
                        last_aggregation_job_id=job.id,
                    )
                )
                continue

            if job.result == IngestionResult.ERROR:
                out.append(
                    StaleStatsRow(
                        module_type_id=r.module_type_id,
                        year=r.year,
                        last_finished_aggregation_at=job.finished_at,
                        why_stale="last_aggregation_failed",
                        last_aggregation_job_id=job.id,
                    )
                )
                continue

            # FINISHED, non-ERROR — only stale if finished_at is missing or
            # older than the cutoff.  Fresh successes don't surface.
            if job.finished_at is None or job.finished_at < cutoff:
                out.append(
                    StaleStatsRow(
                        module_type_id=r.module_type_id,
                        year=r.year,
                        last_finished_aggregation_at=job.finished_at,
                        why_stale="last_aggregation_too_old",
                        last_aggregation_job_id=job.id,
                    )
                )

        return out


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


WhyStaleLiteral = Literal[
    "no_aggregation_ever",
    "last_aggregation_failed",
    "last_aggregation_too_old",
    "pending_aggregation_stuck",
]


class StaleStatsRow(TypedDict):
    """Lightweight stale-aggregation row returned by ``find_stale_aggregations``.

    Mirrors the ``StaleStatsEntry`` Pydantic schema in ``api/v1/data_sync.py``;
    the repo stays Pydantic-free so unit tests don't need the FastAPI stack.
    """

    module_type_id: int
    year: int
    last_finished_aggregation_at: Optional[datetime]
    why_stale: WhyStaleLiteral
    last_aggregation_job_id: Optional[int]


class PipelineGroup(TypedDict):
    """One pipeline returned by ``list_pipelines_paginated`` (#1234).

    ``jobs`` are the raw ORM rows (id-ascending) so the endpoint can run
    ``compute_pipeline_progress`` on them and project the meta allow-list
    at serialization.  ``is_orphan`` flags a ``pipeline_id IS NULL``
    parent that failed before fan-out (rendered as a pipeline-of-one).
    """

    pipeline_id: Optional[UUID]
    is_orphan: bool
    jobs: list[DataIngestionJob]
