"""Background tasks for emission recalculation (Plan 310-C handlers only).

Mirrors the dual-session pattern from ingestion_tasks.py:
- job_session: frequent commits for SSE progress visibility
- data_session: handler-domain writes (committed by the runner
  after the post-handler preemption check)

Plan 310-C registers two handlers via the runner registry
(``emission_recalc``, ``module_emission_recalc``).  The runner
(``app.tasks.runner.run_job``) drives claim, heartbeat, the
preemption check, and the FINISHED-state write — these handlers
only contain the work itself.
"""

from typing import Optional
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    Pipeline,
    TargetType,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._chain import AGGREGATION_DEDUP, chain_job
from app.tasks._locks import acquire_factor_recalc_lock
from app.tasks.registry import register
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Plan 310-C registered handlers (additive — coexist with the legacy
# functions below until the endpoint+poller cutover PR removes them).
# ---------------------------------------------------------------------------


async def _is_last_recalc_sibling(
    job: DataIngestionJob,
    *,
    helper_session: AsyncSession | None = None,
) -> bool:
    """In-pipeline aggregation coalesce gate (#1236 Phase 4A.1).

    Returns ``True`` only for the LAST ``emission_recalc`` sibling of a
    pipeline (where "last" = exactly ``pipeline.expected_recalc``
    siblings have stamped ``meta.recalc_work_complete=True``). Others
    return ``False`` so they skip the aggregation chain.

    Why: today every recalc child chains its own aggregation. Because
    ``AGGREGATION_DEDUP`` only blocks concurrently-active rows, the
    aggregations run *sequentially* (3× per upload in real data) and
    the early ones see partial ``data_entry_emissions`` state. The
    single trailing aggregation chained by the last sibling sees the
    final post-all-recalcs state — correct and 3× fewer aggregations.

    Phase 5B (#1236): the expected count moved from
    ``parent.meta.recalc_jobs_chained`` to ``pipeline.expected_recalc``
    (the ``pipelines`` row column written by ``recompute_pipeline_status``).
    The lock target moved correspondingly — ``SELECT … FOR UPDATE``
    on the ``pipelines`` row serialises siblings.  If the lock had
    stayed on the parent ``data_ingestion_jobs`` row while the read
    moved, two concurrent siblings could both see "I'm last" and
    chain 2 aggregations — silently regressing 4A.1.

    Falls back to ``True`` (always chain — preserves prior behavior)
    when: no ``pipeline_id``, no ``Pipeline`` row, or
    ``pipeline.expected_recalc`` is NULL (never written, e.g. legacy
    pipelines pre-Phase-5A).  Legacy/orphan jobs keep working.

    Race safety: a *fresh* session opens, ``SELECT pipelines … FOR
    UPDATE`` serialises the count-and-decide section across siblings;
    each sibling flushes its own ``recalc_work_complete=True`` inside
    that lock, then commits — making the increment durably visible to
    the next sibling.  The lock is narrow (single short transaction),
    independent of the outer handler's data_session.
    """
    if job.pipeline_id is None or job.id is None:
        return True
    # Same mock-vs-prod gate as ``_build_aggregation_scope_config`` —
    # MagicMock ``pipeline_id``s used by mock-driven unit tests must
    # not reach the real ``SessionLocal``/asyncpg path; treat as
    # "fall back to chain" so existing handler tests don't open a
    # Postgres connection with an unadaptable MagicMock UUID.
    if not isinstance(job.pipeline_id, UUID):
        return True

    async def _decide(helper: AsyncSession) -> bool:
        pipeline = (
            await helper.execute(
                select(Pipeline).where(Pipeline.id == job.pipeline_id).with_for_update()
            )
        ).scalar_one_or_none()
        if pipeline is None:
            return True
        expected = pipeline.expected_recalc
        if expected is None:
            return True

        # Stamp our own row's meta with the work-complete flag so the
        # NEXT sibling's count sees us.
        my_row = (
            await helper.execute(
                select(DataIngestionJob).where(DataIngestionJob.id == job.id)
            )
        ).scalar_one_or_none()
        if my_row is None:
            return True
        my_row.meta = {**(my_row.meta or {}), "recalc_work_complete": True}
        helper.add(my_row)
        await helper.flush()

        siblings = (
            (
                await helper.execute(
                    select(DataIngestionJob).where(
                        DataIngestionJob.pipeline_id == job.pipeline_id,
                        DataIngestionJob.job_type == "emission_recalc",
                    )
                )
            )
            .scalars()
            .all()
        )
        done = sum(1 for s in siblings if (s.meta or {}).get("recalc_work_complete"))
        return done >= int(expected)

    # Production path: own short-lived session keeps the lock narrow.
    # Tests inject ``helper_session`` to use the SQLite fixture without
    # touching the real engine.
    if helper_session is not None:
        return await _decide(helper_session)
    async with SessionLocal() as helper:
        decision = await _decide(helper)
        await helper.commit()
        return decision


async def _build_aggregation_scope_config(
    job: DataIngestionJob,
    my_affected_module_ids: list[int],
    *,
    helper_session: AsyncSession | None = None,
) -> Optional[dict]:
    """4A.4 — build the chain config for the trailing aggregation job.

    The last recalc sibling chains the aggregation BEFORE the runner
    commits its own ``finish_job``. So a sibling-query made by the
    aggregation later would miss THIS recalc's ``affected_module_ids``
    (not yet visible in the DB). Sidestep the race by building the
    full union here — earlier FINISHED siblings (visible) **plus**
    our own ids (from local ``stats``, since the in-memory recalc
    workflow just produced them) — and embedding it in the
    aggregation's ``meta.config``. The aggregation reads from its own
    meta first; the sibling-query stays as a legacy fallback.

    Returns ``None`` when the union is empty AND there are no
    FINISHED siblings to consult — preserves the legacy "full slice"
    behavior for ad-hoc / single-det runs without a meaningful scope.
    Returns ``{"affected_module_ids": [...]}`` otherwise (empty list
    is meaningful: "no modules touched, do nothing" — which is the
    optimized correct behavior, not the legacy fallback).
    """
    union: set[int] = {i for i in (my_affected_module_ids or []) if isinstance(i, int)}
    # ``isinstance(..., UUID)`` is the production-vs-mock gate: real
    # rows carry a UUID; unit-test ``MagicMock`` doesn't. Without this
    # the helper would open ``SessionLocal`` against the production
    # engine in mock-driven tests and emit psycopg errors trying to
    # bind a MagicMock to ``pipeline_id_1``.
    if (
        not isinstance(job.pipeline_id, UUID)
        or job.id is None
        or not isinstance(job.id, int)
    ):
        return {"affected_module_ids": sorted(union)} if union else None

    async def _gather(helper: AsyncSession) -> bool:
        """Returns True if at least one FINISHED sibling was seen
        (so we know an empty union means 'truly nothing to do')."""
        siblings = (
            (
                await helper.execute(
                    select(DataIngestionJob).where(
                        DataIngestionJob.pipeline_id == job.pipeline_id,
                        DataIngestionJob.job_type == "emission_recalc",
                        DataIngestionJob.id != job.id,
                        DataIngestionJob.state == IngestionState.FINISHED,
                    )
                )
            )
            .scalars()
            .all()
        )
        for s in siblings:
            recalc = (s.meta or {}).get("recalculation") or {}
            ids = recalc.get("affected_module_ids")
            if isinstance(ids, list):
                for i in ids:
                    if isinstance(i, int):
                        union.add(i)
        return bool(siblings)

    if helper_session is not None:
        had_siblings = await _gather(helper_session)
    else:
        async with SessionLocal() as helper:
            had_siblings = await _gather(helper)

    # If we saw FINISHED siblings OR we have our own affected ids, the
    # caller should scope precisely (even if the union is empty —
    # "nothing to do" is a real answer). Only return None when there's
    # nothing useful at all, so the aggregation falls back to the full
    # slice — preserves the legacy / ad-hoc behavior.
    if had_siblings or my_affected_module_ids is not None:
        return {"affected_module_ids": sorted(union)}
    return None


@register("emission_recalc")
async def emission_recalc_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Plan 310-C handler — single ``(data_entry_type, year)`` recalc.

    Reads scope from the job row.  The runner has already claimed the
    job (state=RUNNING, attempts++, started_at stamped via PR #1026's
    atomic claim), so this handler does not call ``claim_job`` and
    must not write the FINISHED state — both responsibilities belong
    to ``run_job``.

    Returns the ``meta`` dict the runner will persist to
    ``DataIngestionJob.meta``.  ``status_message`` and ``result``
    keys are read by the runner for the FINISHED-state write.
    """
    if job.id is None:
        raise ValueError("emission_recalc: job has no id")
    if job.data_entry_type_id is None or job.year is None:
        raise ValueError(
            f"emission_recalc job {job.id} missing data_entry_type_id or year"
        )

    data_entry_type = DataEntryTypeEnum(job.data_entry_type_id)
    job_repo = DataIngestionRepository(job_session)

    # In-progress status update (visible to the SSE stream); commit
    # immediately on job_session so subscribers see it before the
    # workflow returns.
    await job_repo.update_ingestion_job(
        job_id=job.id,
        status_message="Recalculating emissions...",
        metadata={},
    )
    await job_session.commit()

    # 4B — per-``(module, year)`` advisory lock: blocks while any
    # concurrent ``factor_ingest`` for the same scope is mid-write,
    # so this recalc reads complete factor values instead of the
    # half-loaded state. Held until ``data_session`` commits (runner
    # does that after this handler returns) — covers the whole
    # factor-read window inside the workflow.
    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=job.module_type_id,
        year=job.year,
        handler_label=f"emission_recalc job {job.id}",
    )

    logger.info(
        f"emission_recalc handler (job {job.id}): "
        f"running workflow for det={data_entry_type.name}/year={job.year}"
    )
    svc = EmissionRecalculationWorkflow(data_session)
    stats = await svc.recalculate_for_data_entry_type(data_entry_type, job.year)

    result = (
        IngestionResult.SUCCESS if stats["errors"] == 0 else IngestionResult.WARNING
    )

    # Plan 310-D — chain the aggregation handler instead of calling
    # ``recompute_stats`` inline (the workflow no longer does it
    # either).  ``dedup_config=AGGREGATION_DEDUP`` collapses N
    # concurrent aggregation jobs for the same (module, year) into
    # one — when ``factor_ingest`` fans out N ``emission_recalc``
    # children, each would otherwise queue its own follow-up
    # aggregation.  The partial unique index ``uq_aggregation_active``
    # covers NOT_STARTED/QUEUED/RUNNING rows so the first child wins
    # and the rest skip; the aggregation runs once after the fan-out
    # (or while later siblings are still finishing — it reads the
    # current snapshot of ``data_entry_emissions`` and produces
    # correct stats for that snapshot, with the dedup window reopening
    # on FINISHED).
    #
    # Chain on WARNING as well as SUCCESS — a 10k-row reupload that
    # fails on a single entry flips ``result`` to WARNING, but the
    # other 9999 rows have already been recomputed and
    # ``carbon_reports.stats`` would stay stale forever if we skipped
    # aggregation here.  Aligns with ``module_emission_recalc_handler``
    # below which uses the same ``!= ERROR`` gate.
    #
    # Skip when ``module_type_id`` is missing — every endpoint pins
    # it for emission_recalc, but a defensive log + skip is safer
    # than crashing the parent's FINISHED write.  The recalc itself
    # already succeeded; the operator sees the missing aggregation
    # via the dashboard's "stats stale" badge if they need it.
    if job.module_type_id is not None and result != IngestionResult.ERROR:
        # #1236 Phase 4A.1 — only the LAST emission_recalc sibling of
        # a pipeline chains the aggregation. Earlier siblings stamp
        # ``meta.recalc_work_complete=True`` and skip; the last one
        # sees the final ``data_entry_emissions`` state and runs one
        # trailing aggregation (was 3 sequential aggregations per
        # upload). ``AGGREGATION_DEDUP`` remains the safety net for
        # the (rare) race where two siblings both observe themselves
        # as last.
        if await _is_last_recalc_sibling(job):
            # 4A.4 — embed the FULL affected_module_ids union (including
            # MY contribution, taken from local ``stats`` since my
            # runner-``finish_job`` hasn't committed my meta yet) in
            # the aggregation job's config. The aggregation handler
            # reads from its OWN meta first (no sibling-query race) —
            # see ``aggregation_tasks.aggregation_handler``.
            agg_config = await _build_aggregation_scope_config(
                job, stats.get("affected_module_ids") or []
            )
            await chain_job(
                job,
                job_type="aggregation",
                module_type_id=job.module_type_id,
                year=job.year,
                config=agg_config,
                session=job_session,
                dedup_config=AGGREGATION_DEDUP,
            )
        else:
            logger.info(
                f"emission_recalc job {job.id}: not the last sibling — "
                "skipping aggregation chain (coalesced to the trailing "
                "sibling per Phase 4A.1)"
            )
    elif job.module_type_id is None:
        logger.warning(
            f"emission_recalc job {job.id}: no module_type_id — "
            "skipping aggregation chain"
        )

    # Phase 5B (#1236) — ``aggregation_job_id`` dropped from meta;
    # ``compute_pipeline_progress`` reads aggregation completion
    # directly from the aggregation job rows in this pipeline.
    return {
        "status_message": "Emission recalculation completed",
        "result": result,
        "recalculation": stats,
    }


@register("module_emission_recalc")
async def module_emission_recalc_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Plan 310-C handler — module-level bulk recalc across N data
    entry types in sequence.

    Reads ``data_entry_type_ids`` from ``job.meta['config']`` (set
    by the endpoint that creates the job).  Same per-type isolation
    as the legacy ``run_module_recalculation_task``: a single failing
    type never aborts the others, errors are accumulated.

    Creates per-type stub FINISHED jobs so
    ``recalc_jobs_sub`` / ``get_recalculation_status_by_year``
    (which exclude rows with ``data_entry_type_id IS NULL``) can
    match the module-level work back to specific types.
    """
    if job.id is None:
        raise ValueError("module_emission_recalc: job has no id")
    if job.module_type_id is None or job.year is None:
        raise ValueError(
            f"module_emission_recalc job {job.id} missing module_type_id or year"
        )
    config = (job.meta or {}).get("config") or {}
    data_entry_type_ids: list[int] = list(config.get("data_entry_type_ids") or [])
    if not data_entry_type_ids:
        raise ValueError(
            f"module_emission_recalc job {job.id} missing config.data_entry_type_ids"
        )

    job_repo = DataIngestionRepository(job_session)

    # 4B — same per-``(module, year)`` advisory lock as the per-det
    # recalc handler: held until ``data_session`` commits so every
    # det in the bulk loop reads factors that are not mid-write by a
    # concurrent ``factor_ingest`` for the same scope.
    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=job.module_type_id,
        year=job.year,
        handler_label=f"module_emission_recalc job {job.id}",
    )

    svc = EmissionRecalculationWorkflow(data_session)
    n = len(data_entry_type_ids)
    per_type_stats: dict[int, dict] = {}
    total_errors = 0
    total_recalculated = 0

    for i, det_id in enumerate(data_entry_type_ids, start=1):
        data_entry_type = DataEntryTypeEnum(det_id)
        await job_repo.update_ingestion_job(
            job_id=job.id,
            status_message=f"Recalculating {data_entry_type.name} ({i}/{n})...",
            metadata={},
        )
        await job_session.commit()

        try:
            async with data_session.begin_nested():
                stats = await svc.recalculate_for_data_entry_type(
                    data_entry_type, job.year
                )
            per_type_stats[det_id] = stats
            total_errors += stats["errors"]
            total_recalculated += stats["recalculated"]
        except Exception as exc:
            logger.error(
                f"module_emission_recalc job {job.id}: type {det_id} "
                f"failed entirely: {exc}",
                exc_info=True,
            )
            per_type_stats[det_id] = {
                "recalculated": 0,
                "modules_refreshed": 0,
                "errors": -1,  # -1 signals a fatal type-level error
                "error_details": [{"error": str(exc)}],
            }
            total_errors += 1

    # Per-type stub FINISHED jobs so the recalc-status query can match
    # the module-level work back to specific data_entry_type_ids.
    for det_id, stats in per_type_stats.items():
        if stats["errors"] == -1:
            type_result = IngestionResult.ERROR
        elif stats["errors"] > 0:
            type_result = IngestionResult.WARNING
        else:
            type_result = IngestionResult.SUCCESS
        type_job = DataIngestionJob(
            module_type_id=job.module_type_id,
            data_entry_type_id=det_id,
            year=job.year,
            ingestion_method=IngestionMethod.computed,
            target_type=TargetType.DATA_ENTRIES,
            entity_type=EntityType.MODULE_PER_YEAR,
            state=IngestionState.FINISHED,
            result=type_result,
            status_message=f"Bulk recalculation via module job {job.id}",
            # Phase 5B (#1236) — ``parent_job_id`` dropped from meta;
            # readers identify parents as the lowest-id job per pipeline.
            meta={"recalculation": stats},
        )
        created = await job_repo.create_ingestion_job(type_job)
        await job_repo.mark_job_as_current(created)

    types_with_fatal = [d for d, s in per_type_stats.items() if s["errors"] == -1]
    if len(types_with_fatal) == n:
        final_result = IngestionResult.ERROR
    elif total_errors > 0:
        final_result = IngestionResult.WARNING
    else:
        final_result = IngestionResult.SUCCESS

    # Plan 310-D — chain a single deduplicated aggregation child for
    # the module + year scope.  Module-level recalc covers N data
    # entry types in sequence; we want one aggregation pass at the
    # end, not one per type.  ``dedup_config=AGGREGATION_DEDUP`` would
    # also collapse concurrent fan-outs to the same scope, but in this
    # handler we only ever issue one chain so it's primarily a
    # safety net.
    if final_result != IngestionResult.ERROR:
        await chain_job(
            job,
            job_type="aggregation",
            module_type_id=job.module_type_id,
            year=job.year,
            session=job_session,
            dedup_config=AGGREGATION_DEDUP,
        )

    # Phase 5B (#1236) — ``aggregation_job_id`` dropped from meta;
    # progress derivation reads aggregation rows from the job table.
    return {
        "status_message": "Module emission recalculation completed",
        "result": final_result,
        "recalculation": per_type_stats,
        "total_recalculated": total_recalculated,
        "total_errors": total_errors,
    }
