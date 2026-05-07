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

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._chain import chain_job
from app.tasks.registry import register
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Plan 310-C registered handlers (additive — coexist with the legacy
# functions below until the endpoint+poller cutover PR removes them).
# ---------------------------------------------------------------------------


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
    # either).  ``dedup_active=True`` collapses N concurrent
    # aggregation jobs for the same (module, year) into one — when
    # ``factor_ingest`` fans out N ``emission_recalc`` children, each
    # would otherwise queue its own follow-up aggregation.  The
    # partial unique index ``uq_aggregation_active`` covers
    # NOT_STARTED/QUEUED/RUNNING rows so the first child wins and the
    # rest skip; the aggregation runs once after the fan-out (or
    # while later siblings are still finishing — it reads the current
    # snapshot of ``data_entry_emissions`` and produces correct stats
    # for that snapshot, with the dedup window reopening on
    # FINISHED).
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
    chained_aggregation_id = None
    if job.module_type_id is not None and result != IngestionResult.ERROR:
        chained_aggregation_id = await chain_job(
            job,
            job_type="aggregation",
            module_type_id=job.module_type_id,
            year=job.year,
            session=job_session,
            dedup_active=True,
        )
    elif job.module_type_id is None:
        logger.warning(
            f"emission_recalc job {job.id}: no module_type_id — "
            "skipping aggregation chain"
        )

    return {
        "status_message": "Emission recalculation completed",
        "result": result,
        "recalculation": stats,
        "aggregation_job_id": chained_aggregation_id,
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
            meta={"parent_job_id": job.id, "recalculation": stats},
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
    # end, not one per type.  ``dedup_active=True`` would also
    # collapse concurrent fan-outs to the same scope, but in this
    # handler we only ever issue one chain so it's primarily a
    # safety net.
    chained_aggregation_id = None
    if final_result != IngestionResult.ERROR:
        chained_aggregation_id = await chain_job(
            job,
            job_type="aggregation",
            module_type_id=job.module_type_id,
            year=job.year,
            session=job_session,
            dedup_active=True,
        )

    return {
        "status_message": "Module emission recalculation completed",
        "result": final_result,
        "recalculation": per_type_stats,
        "total_recalculated": total_recalculated,
        "total_errors": total_errors,
        "aggregation_job_id": chained_aggregation_id,
    }
