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

from typing import Optional

from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionResult,
    IngestionState,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.tasks.registry import register

# #1236 Phase 4A.2 — per-year advisory-lock namespace. Using the
# 2-int variant ``pg_advisory_xact_lock(category, year)`` so the lock
# space is namespaced and can't collide with unrelated advisory-lock
# users in the same DB.
_AGGREGATION_LOCK_CATEGORY = 1236


async def _collect_affected_module_ids(
    pipeline_id, session: AsyncSession
) -> Optional[set[int]]:
    """4A.3 — union of ``affected_module_ids`` from FINISHED recalc siblings.

    Each ``emission_recalc`` records the precise ``carbon_report_module``
    ids whose ``data_entry_emissions`` it touched (in
    ``meta.recalculation.affected_module_ids``). With Phase 4A.1
    in-pipeline coalescing, the aggregation runs once after every
    recalc sibling has finished — so every contributor's affected-ids
    list is already durably committed and the union is the *precise*
    set of modules whose stats are stale.

    Returns ``None`` when no recalc sibling carries that metadata
    (legacy / orphan / pipeline_id missing) so the caller falls back
    to the full ``(module_type_id, year)`` module list — preserves
    prior behavior on legacy paths.
    """
    if pipeline_id is None:
        return None
    siblings = (
        (
            await session.execute(
                select(DataIngestionJob).where(
                    DataIngestionJob.pipeline_id == pipeline_id,
                    DataIngestionJob.job_type == "emission_recalc",
                    DataIngestionJob.state == IngestionState.FINISHED,
                )
            )
        )
        .scalars()
        .all()
    )
    union: set[int] = set()
    any_meta = False
    for s in siblings:
        recalc = (s.meta or {}).get("recalculation") or {}
        ids = recalc.get("affected_module_ids")
        if isinstance(ids, list):
            any_meta = True
            for i in ids:
                if isinstance(i, int):
                    union.add(i)
    return union if any_meta else None


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
    candidates = await svc.list_modules_for(
        module_type_id=job.module_type_id, year=job.year
    )

    # 4A.4 — read the precise union from OUR OWN ``meta.config`` first
    # (set by the last recalc sibling at chain time so the last
    # sibling's own contribution is included — sibling-query couldn't
    # see it yet, runner-``finish_job`` is pending). Falls back to
    # the sibling-query helper (4A.3) for legacy aggregations that
    # weren't passed an explicit scope at chain time.
    own_config = (job.meta or {}).get("config") or {}
    own_scope = own_config.get("affected_module_ids")
    affected_scope: Optional[set[int]]
    if isinstance(own_scope, list):
        scope_set: set[int] = {int(i) for i in own_scope if isinstance(i, int)}
        logger.debug(
            f"aggregation handler (job {job.id}): scope from own "
            f"meta.config.affected_module_ids ({len(scope_set)} ids)"
        )
        affected_scope = scope_set
    else:
        # 4A.3 fallback — sibling-query. Misses the last sibling's
        # contribution when the chain happens before that sibling's
        # finish_job commit, but better than full-slice for legacy.
        affected_scope = await _collect_affected_module_ids(
            job.pipeline_id, data_session
        )
    if affected_scope is not None:
        affected = [m for m in candidates if m.id in affected_scope]
        logger.info(
            f"aggregation handler (job {job.id}): scoped to "
            f"{len(affected)}/{len(candidates)} module(s) via recalc "
            f"affected_module_ids"
        )
    else:
        affected = candidates
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
