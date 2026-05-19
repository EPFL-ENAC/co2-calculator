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

from typing import Iterable, Literal, TypedDict

from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionResult,
    IngestionState,
)

PhaseLabel = Literal["data", "emissions", "aggregation"]

#: Job types that can be the root of a pipeline (no parent_job_id).
_ROOT_JOB_TYPES = {"csv_ingest", "api_ingest", "factor_ingest"}

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
    """The pipeline's parent: the row with no ``parent_job_id``.

    Falls back to the lowest-id root-typed job when meta is absent
    (legacy rows / defensive — every chained child records
    ``parent_job_id``, so a row lacking it is the root).
    """
    rootless = [j for j in jobs if _meta(j).get("parent_job_id") is None]
    candidates = rootless or [j for j in jobs if (j.job_type or "") in _ROOT_JOB_TYPES]
    if not candidates:
        return None
    # ``id`` can be None only for unpersisted rows (never here); the
    # ``or 0`` keeps mypy happy and is harmless for real rows.
    return min(candidates, key=lambda j: j.id or 0)


def compute_pipeline_progress(
    jobs: Iterable[DataIngestionJob],
) -> PipelineProgress:
    """Compute the authoritative phase/done/error for a pipeline.

    ``jobs`` is every row sharing one ``pipeline_id`` (any order).

    Completion rules:

    - **Phase 1 (data)** done ⇔ parent FINISHED.
    - **Phase 2 (emissions)** done ⇔ parent FINISHED *and* the number
      of FINISHED ``emission_recalc`` children ≥ the parent's
      ``meta.recalc_jobs_chained`` (the count of children this
      pipeline actually *owns* — dedup-skipped targets are owned by an
      earlier pipeline and intentionally excluded, so 0 ⇒ phase 2 is
      vacuously satisfied).  When the parent is FINISHED but the
      counter is absent (legacy / non-ingest root), fall back to
      "every recalc row present is FINISHED".
    - **Phase 3 (aggregation)** done ⇔ phase 2 done *and* every
      aggregation referenced by a FINISHED recalc
      (``meta.aggregation_job_id``) is itself present and FINISHED.
    - ``done`` ⇔ phase 3 done **or** any job is FINISHED+ERROR (a
      broken chain spawns no further children, so an error anywhere is
      terminal — the UI must stop the spinner and surface failure).
    """
    jobs = list(jobs)
    has_error = any(_is_finished_error(j) for j in jobs)

    root = _find_root(jobs)
    if root is None:
        # No identifiable parent — treat as not-started rather than
        # crash the stream; the dashboard simply keeps polling.
        return PipelineProgress(
            phase=1,
            phases_total=3,
            phase_label="data",
            done=has_error,
            has_error=has_error,
        )

    recalc_jobs = [j for j in jobs if j.job_type == "emission_recalc"]
    aggregation_jobs = {
        j.id: j for j in jobs if j.job_type == "aggregation" and j.id is not None
    }

    phase1_done = _is_finished(root)

    # Expected owned recalc children. ``recalc_jobs_chained`` is
    # written by the parent handler's return meta (merged on
    # finish_job); absent until the parent is FINISHED.
    expected_recalc = _meta(root).get("recalc_jobs_chained")
    finished_recalc = [j for j in recalc_jobs if _is_finished(j)]
    if expected_recalc is None:
        # Legacy / non-ingest root: best-effort — done when every
        # recalc row we can see is FINISHED (and at least the parent
        # is FINISHED so the fan-out has been issued).
        phase2_done = phase1_done and len(finished_recalc) == len(recalc_jobs)
    else:
        phase2_done = phase1_done and len(finished_recalc) >= int(expected_recalc)

    # Aggregations are only expected for recalc children that actually
    # chained one (success/warning, module known). A FINISHED recalc
    # records ``aggregation_job_id`` (None when it dedup-skipped or
    # skipped on error) in its meta.
    expected_agg_ids = {
        agg_id
        for j in finished_recalc
        if (agg_id := _meta(j).get("aggregation_job_id")) is not None
    }
    aggregations_done = all(
        agg_id in aggregation_jobs and _is_finished(aggregation_jobs[agg_id])
        for agg_id in expected_agg_ids
    )
    phase3_done = phase2_done and aggregations_done

    if not phase1_done:
        phase = 1
    elif not phase2_done:
        phase = 2
    else:
        phase = 3

    return PipelineProgress(
        phase=phase,
        phases_total=3,
        phase_label=_PHASE_LABELS[phase],
        done=phase3_done or has_error,
        has_error=has_error,
    )
