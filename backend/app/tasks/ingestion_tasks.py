"""Background tasks for data ingestion (Plan 310-C runner cutover).

Plan 310-C unifies dispatch under ``run_job(job_id)``.  This module
registers three handlers — one per ingestion shape:

- ``csv_ingest``    — CSV data-entry upload
- ``api_ingest``    — API data-entry ingest (e.g. travel)
- ``factor_ingest`` — Factor CSV/API upsert (post-success: fan out
  emission_recalc children via ``chain_job``).

All three share the same ingest body (``_run_ingest``) since the only
difference between them at the task layer is the post-success fan-out.
The provider class is resolved at handler time from
``job.meta["provider_name"]`` — set by the endpoint when it creates
the job.  Endpoints stamp the matching ``job_type`` so the runner's
registry lookup hits the right handler.
"""

from typing import Any, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionResult,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.services.data_ingestion.provider_factory import ProviderFactory
from app.tasks._chain import EMISSION_RECALC_DEDUP, chain_job
from app.tasks._locks import acquire_factor_recalc_lock
from app.tasks.registry import register

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Plan 310-C registered handlers
# ---------------------------------------------------------------------------


@register("csv_ingest")
async def csv_ingest_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """CSV data-entry ingest with post-success ``emission_recalc`` fan-out.

    Plan 310-D — once the provider commits its data_entries, chain
    one ``emission_recalc`` child per affected (module, det) so the
    runner-driven aggregation handler can pick up the new rows.
    The provider itself no longer writes data_entry_emissions when
    ``BULK_PATH_PURE_ASYNC`` is set (the runner-driven recalc owns
    that table); skipping the fan-out here would leave the new
    data_entries un-aggregated.

    Mirrors ``factor_ingest_handler``'s scope-resolution shape: a
    job with ``data_entry_type_id`` pinned chains a single child for
    that pair; a multi-det module upload (det NULL) fans out one
    child per det in ``MODULE_TYPE_TO_DATA_ENTRY_TYPES``.
    """
    meta = await _run_ingest(job, job_session, data_session)
    if meta.get("result") == IngestionResult.ERROR:
        # No data_entries committed (or partial state we don't trust)
        # — nothing to recalc against.  Runner will mark FINISHED+ERROR.
        return meta

    # Phase 5B (#1236) — chained count no longer threaded through
    # ``meta.recalc_jobs_chained``; ``recompute_pipeline_status``
    # derives the same value from the live job count and writes it to
    # ``pipelines.expected_recalc``.  The call remains for its
    # side-effect of dispatching the recalc fan-out.
    await _chain_emission_recalc_for_data_ingest(job, job_session)
    return meta


@register("api_ingest")
async def api_ingest_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """API data-entry ingest (e.g. travel) with post-success
    ``emission_recalc`` fan-out.

    Same body as ``csv_ingest_handler`` — provider class differs,
    fan-out shape is identical (the recalc workflow operates on the
    same (det, year) slice regardless of how the data_entries
    arrived).
    """
    meta = await _run_ingest(job, job_session, data_session)
    if meta.get("result") == IngestionResult.ERROR:
        return meta

    await _chain_emission_recalc_for_data_ingest(job, job_session)
    return meta


@register("factor_ingest")
async def factor_ingest_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Factor CSV/API upsert with post-success emission_recalc fan-out.

    Runs the shared ingest body, then — on success — chains one
    ``emission_recalc`` child per stale ``(module, det)`` combo via
    ``chain_job``.  The fan-out scope follows the parent job's
    ``module_type_id`` / ``data_entry_type_id`` (Plan 310-B logic):

    - Both set → single child for that exact pair (the parent factor
      job is still RUNNING here, so the recalc-status query would
      miss it; short-circuit to the parent's own scope).
    - Module set, det NULL → expand to one child per det in the
      module via ``MODULE_TYPE_TO_DATA_ENTRY_TYPES`` (multi-type
      factor file).
    - Both NULL → consult ``get_recalculation_status_by_year`` for
      anything stale (admin-style trigger).
    """
    # 4B — per-``(module, year)`` advisory lock acquired BEFORE the
    # factor write begins, so any concurrent ``emission_recalc`` for
    # the same scope blocks at its own lock-acquisition (in
    # ``emission_recalc_handler``) instead of reading half-written
    # factor values. Lock released when the runner commits
    # ``data_session`` after this handler returns.
    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=job.module_type_id,
        year=job.year,
        handler_label=f"factor_ingest job {job.id}",
    )

    meta = await _run_ingest(job, job_session, data_session)
    if meta.get("result") == IngestionResult.ERROR:
        # Skip fan-out on failure — there's nothing to recalc against.
        return meta
    if job.year is None:
        logger.warning(
            f"factor_ingest job {job.id}: no year on parent — skipping recalc fan-out"
        )
        return meta

    # Phase 5B (#1236) — see csv_ingest_handler; chained count derived
    # from job rows via ``recompute_pipeline_status``, not threaded
    # through meta.
    await _chain_recalc_for_stale(job, job_session)
    return meta


# ---------------------------------------------------------------------------
# Shared ingest helper
# ---------------------------------------------------------------------------


#: Cap on the per-row reason embedded in ``status_message`` so the
#: column stays tractable when row_errors carries a long Postgres
#: traceback.  200 chars is enough for the operator to recognise the
#: failure class without expanding the timeline.
_STATUS_MESSAGE_REASON_CAP = 200


def _sample_row_error_reason(row_errors: list) -> Optional[str]:
    """Pick a representative reason from ``stats.row_errors`` (#1236).

    Row errors are recorded in order; the first one is usually
    representative when the failure mode is uniform (missing factors,
    wrong CSV columns, unknown category).  Capped at
    ``_STATUS_MESSAGE_REASON_CAP`` chars so the status_message column
    doesn't blow up when a reason carries a stack trace.
    """
    if not row_errors:
        return None
    first = row_errors[0]
    reason = first.get("reason") if isinstance(first, dict) else None
    if not reason:
        return None
    if len(reason) > _STATUS_MESSAGE_REASON_CAP:
        reason = reason[: _STATUS_MESSAGE_REASON_CAP - 1] + "…"
    return reason


def finalize_ingest_meta(result: dict) -> dict:
    """Flatten a provider ``ingest()`` return into the handler's meta,
    making ``status_message`` honest (#1236).

    The provider's ``ingest()`` hardcodes ``status_message="Success"``
    whenever it does not *raise* — but a CSV where every row errored
    finishes WITHOUT raising and is classified ERROR/WARNING from the
    row-error stats. A FINISHED job whose result != SUCCESS must not
    claim "Success" — that lie is what pipeline status / ``last_error``
    then propagate (#1219). When result != SUCCESS and the message is
    the generic "Success", replace it with an honest summary from the
    counts the provider already returned, plus a sample reason from
    ``stats.row_errors`` so a lone-orphan parent (pipeline-of-one with
    no ``pipelines.last_error`` to enrich it) carries the real cause
    instead of just "0 inserted, 50 072 skipped".  A real exception-
    path message ("failed: …") never reaches here (it raises upstream),
    so it is preserved.

    Shared by ``_run_ingest`` (csv/api/factor) and
    ``reference_ingest_handler`` — they had two identical copies of
    this join; the duplication is what let the bug exist in one.
    """
    data = result.get("data", {}) or {}
    ingestion_result = data.get("result", IngestionResult.SUCCESS)
    status_message = result.get("status_message", "Success")
    if ingestion_result != IngestionResult.SUCCESS and (
        not status_message or status_message.strip().lower() == "success"
    ):
        rec = "ERROR" if ingestion_result == IngestionResult.ERROR else "WARNING"
        status_message = (
            f"{rec}: {data.get('inserted', 0)} inserted, "
            f"{data.get('skipped', 0)} skipped"
        )
        sample_reason = _sample_row_error_reason(data.get("row_errors") or [])
        if sample_reason:
            status_message += f" — first error: {sample_reason}"
    return {
        "status_message": status_message,
        "result": ingestion_result,
        **data,
    }


async def _run_ingest(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Resolve the provider from ``meta.provider_name`` and run ``ingest``.

    The runner has already claimed the job (state=RUNNING, attempts++,
    started_at stamped via PR #1026's atomic claim) and will write the
    FINISHED state on return.  This helper does NOT call ``claim_job``
    or ``update_ingestion_job(state=FINISHED)`` — both responsibilities
    belong to ``run_job``.

    Returns the ``meta`` dict the runner persists alongside the
    FINISHED-state write.  ``status_message`` and ``result`` keys are
    read by the runner.
    """
    if job.id is None:
        raise ValueError("ingest handler: job has no id")

    job_meta = job.meta or {}
    provider_name = job_meta.get("provider_name")
    if not provider_name:
        raise ValueError(
            f"ingest handler: job {job.id} missing meta.provider_name "
            "(endpoint must set it when creating the job)"
        )

    provider_class = ProviderFactory.get_provider_class(provider_name)
    if not provider_class:
        raise ValueError(
            f"ingest handler: provider class {provider_name!r} not found (job {job.id})"
        )

    job_config = job_meta.get("config") or {}
    provider = provider_class(
        config={**job.__dict__, **job_config, "job_id": job.id},
        user=job.user if hasattr(job, "user") else None,
        job_session=job_session,
        data_session=data_session,
    )
    # The runner is the single FINISHED authority — defer the
    # provider's own state=FINISHED writes (success and error branches
    # both go through ``_update_job`` in the base class).  Without this,
    # ``finished_at`` would stamp at provider-return time (skipping
    # handler-side post-processing), ``factor_ingest``'s chain children
    # would get created AFTER the parent appears FINISHED on the
    # dashboard, and the runner's preempt-check could be bypassed.
    provider.defer_finalize = True
    if hasattr(provider, "set_job_id"):
        await provider.set_job_id(job.id)

    # ``provider.ingest`` still drives ``_update_job(state=RUNNING …)``
    # for SSE progress; only the FINISHED transition is deferred to the
    # runner (see ``defer_finalize`` above).
    filters = job_meta.get("filters") or {}
    result = await provider.ingest(filters)

    return finalize_ingest_meta(result)


# ---------------------------------------------------------------------------
# factor_ingest post-success fan-out
# ---------------------------------------------------------------------------


async def _chain_recalc_for_stale(
    job: DataIngestionJob,
    session: AsyncSession,
) -> int:
    """Fan out one ``emission_recalc`` child per stale ``(module, det)``.

    Returns the number of children chained.  Replaces Plan 310-B's
    ``_enqueue_stale_recalculations`` — the same scope-resolution logic,
    but each target now goes through ``chain_job`` (uniform pipeline_id
    inheritance, runner-driven dispatch, no manual fire_and_forget).

    Each chain passes ``dedup_config=EMISSION_RECALC_DEDUP`` (#1064): the
    partial unique index ``uq_emission_recalc_active`` collapses
    back-to-back factor reuploads for the same ``(module, det, year)``
    into a single pending recalc.  Without this, a user re-uploading
    a corrected factors CSV seconds after the first upload would queue
    a redundant recalc on top of the already-pending one.
    """
    # Late import to avoid circular: module_type → data_ingestion → tasks.
    from app.models.module_type import (
        MODULE_TYPE_TO_DATA_ENTRY_TYPES,
        ModuleTypeEnum,
    )

    # The caller (factor_ingest_handler) only invokes this helper after
    # validating job.year is set.  Re-narrow with an explicit raise
    # rather than ``assert`` — bandit B101 strips assertions under
    # ``python -O``, so a defensive narrowing assert can't be relied on
    # at runtime.  Same pattern as #1027's emission_recalc narrowing fix.
    if job.year is None:
        raise ValueError(
            f"_chain_recalc_for_stale: job {job.id} has no year — "
            "caller must validate before invoking"
        )
    year: int = job.year
    repo = DataIngestionRepository(session)

    # ``targets`` is a heterogeneous list — the synthetic single-type and
    # multi-type rows are plain dicts; the all-stale branch yields
    # ``RecalculationStatusRow`` TypedDicts.  The three downstream keys
    # we read (module_type_id, data_entry_type_id, year) line up across
    # both shapes, so widen to ``dict[str, Any]`` for the iteration.
    targets: list[dict[str, Any]]
    if job.module_type_id is not None and job.data_entry_type_id is not None:
        # Single-type factor upload — the parent tells us exactly which
        # (module, det) just changed.  We do NOT consult
        # ``get_recalculation_status_by_year`` because that helper filters
        # on ``state=FINISHED`` and the parent factor job is still RUNNING
        # at this point in the pipeline (FINISHED stamping happens AFTER
        # fan-out, deliberately, so the new owner closes out cleanly).
        targets = [
            {
                "module_type_id": job.module_type_id,
                "data_entry_type_id": job.data_entry_type_id,
                "year": year,
            }
        ]
    elif job.module_type_id is not None and job.data_entry_type_id is None:
        # Multi-type factor upload (e.g. equipments_factors.csv covers
        # scientific + it + other under module=equipment_electric_consumption).
        # Same RUNNING-parent hazard, different resolution: expand to one
        # target per det via MODULE_TYPE_TO_DATA_ENTRY_TYPES.
        try:
            module = ModuleTypeEnum(job.module_type_id)
        except ValueError:
            logger.warning(
                f"factor_ingest job {job.id}: unknown module_type_id="
                f"{job.module_type_id}; skipping recalc fan-out"
            )
            return 0
        dets = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module, [])
        targets = [
            {
                "module_type_id": job.module_type_id,
                "data_entry_type_id": d.value,
                "year": year,
            }
            for d in dets
        ]
    else:
        # Both NULL — operator wants "anything stale this year".  Only
        # branch that reads from ``get_recalculation_status_by_year``
        # (filters on state=FINISHED), reachable via admin-style triggers.
        rows = await repo.get_recalculation_status_by_year(year)
        targets = [dict(r) for r in rows if r["needs_recalculation"]]

    if not targets:
        logger.info(
            f"factor_ingest job {job.id}: no stale (module, det) "
            f"combos to recalculate for year={year}"
        )
        return 0

    # ``chain_job`` defaults already cover target_type=DATA_ENTRIES,
    # ingestion_method=computed, entity_type=MODULE_PER_YEAR — exactly
    # what an emission_recalc child needs — so we don't pass them.
    # ``emission_recalc_handler`` reads scope from the row's columns
    # (data_entry_type_id, year), not from meta.config, so the config
    # is intentionally minimal.
    # Count only children this pipeline actually created — a
    # dedup-skipped target (``chain_job`` returns ``None``) means an
    # earlier active pipeline already owns that recalc, so it must NOT
    # count toward THIS pipeline's expected fan-out (the
    # pipeline-progress contract keys phase 2 off this number; counting
    # skipped targets would make completion wait forever).
    chained = 0
    for row in targets:
        child_id = await chain_job(
            job,
            job_type="emission_recalc",
            module_type_id=row["module_type_id"],
            data_entry_type_id=row["data_entry_type_id"],
            year=year,
            session=session,
            dedup_config=EMISSION_RECALC_DEDUP,
        )
        if child_id is not None:
            chained += 1
    logger.info(
        f"factor_ingest job {job.id}: chained {chained}/{len(targets)} "
        f"emission_recalc child(ren) for year={year}"
    )
    return chained


# ---------------------------------------------------------------------------
# csv_ingest / api_ingest post-success fan-out
# ---------------------------------------------------------------------------


async def _chain_emission_recalc_for_data_ingest(
    job: DataIngestionJob,
    session: AsyncSession,
) -> int:
    """Fan out ``emission_recalc`` children for a successful data-entry ingest.

    Plan 310-D — replaces the inline emission write the providers
    used to do.  Scope-resolution mirrors ``_chain_recalc_for_stale``
    but without the "anything stale" admin branch; data ingests
    always know which module they wrote against:

    - ``module_type_id`` + ``data_entry_type_id`` set → one child for
      that exact pair.
    - ``module_type_id`` set, ``data_entry_type_id`` NULL → one child
      per det in ``MODULE_TYPE_TO_DATA_ENTRY_TYPES`` (a CSV upload that
      mixes dets within one module — the workflow processes each det
      independently anyway, so fanning out matches its grain).
    - ``module_type_id`` NULL → defensive log + skip; a data-entry
      ingest without a module isn't a shape we expect (every endpoint
      pins module_type_id).  Leaving the data un-recalculated is
      preferable to crashing the parent's FINISHED write.

    Returns the number of children chained (0 on the defensive
    skip).  Year is mandatory for ``emission_recalc`` (the workflow
    queries by ``(data_entry_type_id, year)``); raise rather than
    skip so the misconfigured job surfaces as FINISHED+ERROR.
    """
    if job.id is None:
        raise ValueError("_chain_emission_recalc_for_data_ingest: job has no id")
    if job.year is None:
        raise ValueError(
            f"_chain_emission_recalc_for_data_ingest: job {job.id} has no year — "
            "endpoint must pin year for csv_ingest / api_ingest"
        )
    year: int = job.year

    if job.module_type_id is None:
        logger.warning(
            f"data ingest job {job.id}: no module_type_id on parent — "
            "skipping emission_recalc fan-out"
        )
        return 0

    targets: list[dict[str, Any]]
    if job.data_entry_type_id is not None:
        targets = [
            {
                "module_type_id": job.module_type_id,
                "data_entry_type_id": job.data_entry_type_id,
                "year": year,
            }
        ]
    else:
        # Multi-det data ingest (e.g. headcount.csv covers member +
        # student in one upload).  Late import avoids the
        # data_ingestion → tasks → module_type cycle.
        from app.models.module_type import (
            MODULE_TYPE_TO_DATA_ENTRY_TYPES,
            ModuleTypeEnum,
        )

        try:
            module = ModuleTypeEnum(job.module_type_id)
        except ValueError:
            logger.warning(
                f"data ingest job {job.id}: unknown module_type_id="
                f"{job.module_type_id}; skipping emission_recalc fan-out"
            )
            return 0
        dets = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module, [])
        targets = [
            {
                "module_type_id": job.module_type_id,
                "data_entry_type_id": d.value,
                "year": year,
            }
            for d in dets
        ]

    if not targets:
        logger.info(
            f"data ingest job {job.id}: no (module, det) targets for "
            f"module_type_id={job.module_type_id}/year={year}; "
            "skipping emission_recalc fan-out"
        )
        return 0

    # ``dedup_config`` (Fix #1219): a pre-existing active recalc for
    # this scope now yields a logged no-op (``chain_job`` returns
    # ``None``) instead of an uncaught IntegrityError that poisoned the
    # job_session and stranded the parent.  Mirror the factor path.
    # Count only owned children — see ``_chain_recalc_for_stale``.
    chained = 0
    for row in targets:
        child_id = await chain_job(
            job,
            job_type="emission_recalc",
            module_type_id=row["module_type_id"],
            data_entry_type_id=row["data_entry_type_id"],
            year=year,
            session=session,
            dedup_config=EMISSION_RECALC_DEDUP,
        )
        if child_id is not None:
            chained += 1
    logger.info(
        f"data ingest job {job.id}: chained {chained}/{len(targets)} "
        f"emission_recalc child(ren) for "
        f"module_type_id={job.module_type_id}/year={year}"
    )
    return chained


__all__ = [
    "csv_ingest_handler",
    "api_ingest_handler",
    "factor_ingest_handler",
]
