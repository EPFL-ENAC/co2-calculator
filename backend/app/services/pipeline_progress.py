"""Server-authoritative pipeline-progress computation (Issue #1219).

A data-ingestion *pipeline* is a parent upload job
(``csv_ingest`` / ``api_ingest`` / ``factor_ingest``) plus the
``emission_recalc`` children it fans out, plus the ``aggregation``
grandchild each recalc chains.  Before this module the SSE stream
declared a pipeline "finished" when *every job currently sharing the
pipeline_id was FINISHED* — which fires prematurely in the window
where the parent is FINISHED but its children have not been INSERTed
yet, so the UI flashed green on a pipeline that had only done step 1.

``compute_pipeline_progress`` derives completion from the *expected*
fan-out recorded in job meta (``recalc_jobs_chained`` on the parent,
``aggregation_job_id`` on each recalc — both written by the runner via
``finish_job``), not from a possibly-incomplete snapshot.  It is a
pure function: hand it the rows, get back the phase + done/error
flags.  Consumed by both ``GET /sync/pipelines/{id}`` and the
``/stream`` SSE endpoint so client and server agree on "done".

The model is 3 fixed phases:

1. ``data``        — parent upload FINISHED.
2. ``emissions``   — every owned ``emission_recalc`` child FINISHED.
3. ``aggregation`` — every aggregation referenced by a FINISHED
   recalc is itself FINISHED.
"""

from __future__ import annotations

from typing import Iterable, Literal, Optional, TypedDict

from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionResult,
    IngestionState,
    Pipeline,
    PipelineStatus,
)

PhaseLabel = Literal["data", "emissions", "aggregation"]

#: Terminal ``pipelines.status`` values — Phase-3 read-flip uses these for
#: ``done``/``has_error`` instead of inferring from a possibly-incomplete
#: job snapshot.  PARTIAL = chain completed with some children erroring;
#: FAILED = chain broken (a job FINISHED+ERROR aborted the fan-out).
_TERMINAL_PIPELINE_STATUSES = frozenset(
    {
        PipelineStatus.SUCCESS.value,
        PipelineStatus.PARTIAL.value,
        PipelineStatus.FAILED.value,
    }
)
_ERROR_PIPELINE_STATUSES = frozenset(
    {PipelineStatus.PARTIAL.value, PipelineStatus.FAILED.value}
)

_PHASE_LABELS: dict[int, PhaseLabel] = {
    1: "data",
    2: "emissions",
    3: "aggregation",
}


class PipelineProgress(TypedDict):
    """Authoritative pipeline status — see module docstring."""

    phase: int
    phases_total: int
    phase_label: PhaseLabel
    done: bool
    has_error: bool


def _is_finished(job: DataIngestionJob) -> bool:
    return job.state == IngestionState.FINISHED


def _is_finished_error(job: DataIngestionJob) -> bool:
    return _is_finished(job) and job.result == IngestionResult.ERROR


def _meta(job: DataIngestionJob) -> dict:
    # ``meta`` is a nullable JSON column; normalise to a dict so
    # callers can ``.get`` without a None guard at every site.
    return job.meta or {}


def _find_root(jobs: list[DataIngestionJob]) -> DataIngestionJob | None:
    """The pipeline's parent: the lowest-id job.

    ``chain_job`` creates every fan-out child AFTER the parent, so the
    lowest id is the parent by construction.  Phase 5 dropped the
    previous ``meta.parent_job_id`` and ``_ROOT_JOB_TYPES`` filter — the
    set omitted ``unit_sync`` and ``reference_ingest`` parents, leaving
    those pipelines with no root.  The id-based pick is type-agnostic
    and works for every root job_type.

    ``id`` can be None only for unpersisted rows (never here); the
    ``or 0`` keeps mypy happy and is harmless for real rows.
    """
    if not jobs:
        return None
    return min(jobs, key=lambda j: j.id or 0)


def compute_pipeline_progress(
    jobs: Iterable[DataIngestionJob],
    *,
    pipeline: Optional[Pipeline] = None,
) -> PipelineProgress:
    """Compute the authoritative phase/done/error for a pipeline.

    ``jobs`` is every row sharing one ``pipeline_id`` (any order).

    **Phase-3 read-flip (#1236):** when a ``pipeline`` row is passed,
    ``done`` and ``has_error`` derive from ``pipeline.status`` — the
    durable, recompute-and-stored truth the runner writes
    post-``finish_job`` and the reconciliation cron heals.  Without
    it, both flags fall back to job-derived (the legacy path; used
    for orphans that never minted a ``Pipeline`` row).

    **Phase 5B (#1236):** all three meta keys (``parent_job_id``,
    ``recalc_jobs_chained``, ``aggregation_job_id``) are retired.
    ``expected_recalc`` comes from ``pipeline.expected_recalc``
    (written by ``recompute_pipeline_status`` from the live job
    count); the root is the lowest-id job (``chain_job`` creates
    parents before children by construction); aggregation phase3 is
    derived from the aggregation rows directly.

    Completion rules:

    - **Phase 1 (data)** done ⇔ parent (lowest-id job) FINISHED.
    - **Phase 2 (emissions)** done ⇔ parent FINISHED *and* the number
      of FINISHED ``emission_recalc`` children ≥ the pipeline's
      expected recalc count (``pipeline.expected_recalc`` when
      present, else the live job count — which matches the writer's
      own derivation).  Dedup-skipped targets live under another
      pipeline's id and aren't in ``jobs``, so 0 expected ⇒ phase 2
      vacuously satisfied.
    - **Phase 3 (aggregation)** done ⇔ phase 2 done *and* every
      aggregation row in this pipeline is FINISHED.  Relies on
      4A.1's invariant that the last recalc sibling chains exactly
      one aggregation per pipeline; if that ever changes, this check
      stays semantically correct only by counting ALL aggregation
      rows (any new fan-out must preserve that).
    - ``done`` / ``has_error`` ← ``pipeline.status`` when provided
      (Phase 3 read-flip); fall back to job-derived otherwise.
    """
    jobs = list(jobs)
    has_error_jobs = any(_is_finished_error(j) for j in jobs)

    # Phase 3 read-flip: pipeline.status is authoritative when present.
    # has_error / done come from the table; phase still derives from
    # jobs (no column to read it from yet).
    if pipeline is not None:
        has_error = pipeline.status in _ERROR_PIPELINE_STATUSES
        is_done = pipeline.status in _TERMINAL_PIPELINE_STATUSES
    else:
        has_error = has_error_jobs
        is_done = None  # sentinel: compute from jobs below

    root = _find_root(jobs)
    if root is None:
        # No identifiable parent — treat as not-started rather than
        # crash the stream; the dashboard simply keeps polling.
        return PipelineProgress(
            phase=1,
            phases_total=3,
            phase_label="data",
            done=is_done if is_done is not None else has_error,
            has_error=has_error,
        )

    recalc_jobs = [j for j in jobs if j.job_type == "emission_recalc"]
    aggregation_jobs = [j for j in jobs if j.job_type == "aggregation"]

    phase1_done = _is_finished(root)

    # Phase 5B (#1236) — expected recalc count.  Primary source:
    # ``pipeline.expected_recalc`` (Phase 5A writes it on every
    # recompute).  Fallback for callers that don't pass ``pipeline``
    # (orphans, tests, the writer-side ``recompute_pipeline_status``
    # which can't read its own output): derive from the live job
    # count.  Matches the value the writer would produce by the same
    # rule, so the two paths agree.
    finished_recalc = [j for j in recalc_jobs if _is_finished(j)]
    if pipeline is not None and pipeline.expected_recalc is not None:
        expected_recalc = int(pipeline.expected_recalc)
    else:
        expected_recalc = len(recalc_jobs)
    phase2_done = phase1_done and len(finished_recalc) >= expected_recalc

    # Phase 5B — aggregation phase3 derived from job rows directly,
    # not ``meta.aggregation_job_id``.  4A.1's in-pipeline coalesce
    # chains EXACTLY ONE aggregation per pipeline (the last recalc
    # sibling is the chainer), so "all aggregation rows FINISHED" is
    # the right oracle: 0 aggregations ⇒ vacuously satisfied (every
    # recalc dedup-skipped its aggregation or errored before chaining);
    # 1+ aggregations ⇒ they must all be FINISHED.
    # CAVEAT: if 4A.1's single-aggregation guarantee ever changes
    # (e.g. per-recalc aggregations come back), this check stays
    # correct only because we count ALL aggregation rows — anyone
    # adding fan-out must keep that invariant or update this check.
    aggregations_done = all(_is_finished(j) for j in aggregation_jobs)
    phase3_done = phase2_done and aggregations_done

    if not phase1_done:
        phase = 1
    elif not phase2_done:
        phase = 2
    else:
        phase = 3

    # Phase-3 read-flip: pipeline.status carries ``done`` when present;
    # otherwise fall back to the job-derived oracle (phase3 OR error).
    if is_done is None:
        done = phase3_done or has_error
    else:
        done = is_done

    return PipelineProgress(
        phase=phase,
        phases_total=3,
        phase_label=_PHASE_LABELS[phase],
        done=done,
        has_error=has_error,
    )
