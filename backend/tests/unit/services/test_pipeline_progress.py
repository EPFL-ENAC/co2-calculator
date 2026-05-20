"""Issue #1219 — server-authoritative pipeline progress.

These cover the contract the SSE stream + ``GET /pipelines/{id}`` rely
on so the UI never flashes "success" on a half-done pipeline, and the
zombie/two-recalc scenarios that motivated the fix.
"""

from types import SimpleNamespace

from app.models.data_ingestion import IngestionResult, IngestionState, PipelineStatus
from app.services.pipeline_progress import compute_pipeline_progress

S = IngestionState
R = IngestionResult


def _job(job_id, job_type, state, *, result=None, meta=None):
    """Minimal duck-typed DataIngestionJob for the pure progress fn."""
    return SimpleNamespace(
        id=job_id,
        job_type=job_type,
        state=state,
        result=result,
        meta=meta or {},
    )


def _parent(state, *, recalc_chained=None, result=None):
    meta = {}
    if recalc_chained is not None:
        meta["recalc_jobs_chained"] = recalc_chained
    return _job(1, "csv_ingest", state, result=result, meta=meta)


def _recalc(job_id, state, *, agg_id=None, result=None):
    meta = {"parent_job_id": 1}
    if agg_id is not None:
        meta["aggregation_job_id"] = agg_id
    return _job(job_id, "emission_recalc", state, result=result, meta=meta)


def _agg(job_id, state, *, result=None):
    return _job(job_id, "aggregation", state, result=result, meta={"parent_job_id": 2})


def test_parent_not_started_is_phase_1_not_done():
    p = compute_pipeline_progress([_parent(S.NOT_STARTED)])
    assert p["phase"] == 1
    assert p["phase_label"] == "data"
    assert p["done"] is False
    assert p["has_error"] is False


def test_parent_only_snapshot_does_not_prematurely_complete():
    """THE core UX bug: parent FINISHED, children not yet INSERTed.

    Old "all snapshot jobs FINISHED" logic flashed the module green
    here. The expected-fan-out contract keeps it at phase 2.
    """
    p = compute_pipeline_progress([_parent(S.FINISHED, recalc_chained=2)])
    assert p["phase"] == 2
    assert p["done"] is False


def test_recalc_chained_zero_completes_after_parent():
    """Intentional edge: every recalc target dedup-skipped (owned by an
    earlier pipeline) or unknown module → recalc_jobs_chained == 0 ⇒
    phases 2/3 vacuously satisfied once the parent is done."""
    p = compute_pipeline_progress([_parent(S.FINISHED, recalc_chained=0)])
    assert p["phase"] == 3
    assert p["done"] is True
    assert p["has_error"] is False


def test_two_recalc_partial_is_not_done():
    """Multi-det upload fans out 2 recalcs; only 1 finished → phase 2."""
    jobs = [
        _parent(S.FINISHED, recalc_chained=2),
        _recalc(2, S.FINISHED, agg_id=None),
        _recalc(3, S.RUNNING),
    ]
    p = compute_pipeline_progress(jobs)
    assert p["phase"] == 2
    assert p["done"] is False


def test_zombie_recalc_keeps_pipeline_unfinished():
    """A recalc child stuck RUNNING forever (the zombie) must keep the
    pipeline reported as in-progress — never falsely 'done'."""
    jobs = [
        _parent(S.FINISHED, recalc_chained=1),
        _recalc(2, S.RUNNING),  # zombie
    ]
    p = compute_pipeline_progress(jobs)
    assert p["phase"] == 2
    assert p["done"] is False
    assert p["has_error"] is False


def test_aggregation_pending_is_phase_3_not_done():
    jobs = [
        _parent(S.FINISHED, recalc_chained=1),
        _recalc(2, S.FINISHED, agg_id=99),
        _agg(99, S.RUNNING),
    ]
    p = compute_pipeline_progress(jobs)
    assert p["phase"] == 3
    assert p["done"] is False


def test_full_success_is_done():
    jobs = [
        _parent(S.FINISHED, recalc_chained=2),
        _recalc(2, S.FINISHED, agg_id=99),
        _recalc(3, S.FINISHED, agg_id=100),
        _agg(99, S.FINISHED),
        _agg(100, S.FINISHED),
    ]
    p = compute_pipeline_progress(jobs)
    assert p["phase"] == 3
    assert p["done"] is True
    assert p["has_error"] is False


def test_recalc_with_no_aggregation_chained_still_completes():
    """A recalc that didn't chain an aggregation (dedup-skip / WARNING
    with module known but agg already pending) records
    ``aggregation_job_id=None`` — phase 3 must not wait on it."""
    jobs = [
        _parent(S.FINISHED, recalc_chained=1),
        _recalc(2, S.FINISHED, agg_id=None),
    ]
    p = compute_pipeline_progress(jobs)
    assert p["done"] is True


def test_parent_error_is_terminal():
    jobs = [_parent(S.FINISHED, recalc_chained=0, result=R.ERROR)]
    p = compute_pipeline_progress(jobs)
    assert p["has_error"] is True
    assert p["done"] is True


def test_recalc_error_is_terminal_even_without_aggregation():
    """Recalc FINISHED+ERROR → no aggregation chained; pipeline is
    done-with-error, UI must stop the spinner and show failure."""
    jobs = [
        _parent(S.FINISHED, recalc_chained=1),
        _recalc(2, S.FINISHED, result=R.ERROR),
    ]
    p = compute_pipeline_progress(jobs)
    assert p["has_error"] is True
    assert p["done"] is True


def test_legacy_no_counter_falls_back_to_present_children():
    """Non-ingest / legacy root without ``recalc_jobs_chained``: done
    when every recalc row present is FINISHED (best-effort)."""
    parent = _job(1, "factor_ingest", S.FINISHED, meta={})
    jobs = [parent, _recalc(2, S.FINISHED, agg_id=None)]
    p = compute_pipeline_progress(jobs)
    assert p["done"] is True

    jobs_pending = [parent, _recalc(2, S.RUNNING)]
    assert compute_pipeline_progress(jobs_pending)["done"] is False


def test_empty_pipeline_is_safe():
    p = compute_pipeline_progress([])
    assert p["phase"] == 1
    assert p["done"] is False


# ---------------------------------------------------------------------------
# Phase 3 read-flip (#1236) — ``pipeline.status`` is authoritative when passed.
# ---------------------------------------------------------------------------


def _pl(status):
    """Minimal duck-typed Pipeline row for the read-flip branch."""
    return SimpleNamespace(status=status)


def test_pipeline_status_success_marks_done_even_if_jobs_lag():
    """Read-flip: pipeline.status=SUCCESS is authoritative.

    Stage: snapshot may show a stragger RUNNING child while
    ``pipelines.status`` already reconciled to SUCCESS (race between the
    runner's isolated post-finish write and the SSE poll picking up the
    pre-write snapshot).  With the row passed in, ``done`` is the
    table's truth, not the snapshot's.
    """
    jobs = [_parent(S.FINISHED, recalc_chained=2), _recalc(2, S.FINISHED, agg_id=10)]
    p = compute_pipeline_progress(jobs, pipeline=_pl(PipelineStatus.SUCCESS.value))
    assert p["done"] is True
    assert p["has_error"] is False


def test_pipeline_status_failed_marks_done_and_has_error():
    jobs = [_parent(S.RUNNING)]
    p = compute_pipeline_progress(jobs, pipeline=_pl(PipelineStatus.FAILED.value))
    assert p["done"] is True
    assert p["has_error"] is True


def test_pipeline_status_partial_marks_done_and_has_error():
    jobs = [_parent(S.FINISHED, recalc_chained=2)]
    p = compute_pipeline_progress(jobs, pipeline=_pl(PipelineStatus.PARTIAL.value))
    assert p["done"] is True
    assert p["has_error"] is True


def test_pipeline_status_running_keeps_not_done_even_if_jobs_all_finished():
    """Inverse race: snapshot all FINISHED, ``pipelines.status`` not yet
    advanced (the runner's isolated write hasn't landed; the next sweep
    will heal it).  The table is authoritative — keep the spinner."""
    jobs = [
        _parent(S.FINISHED, recalc_chained=1),
        _recalc(2, S.FINISHED, agg_id=10),
        _agg(10, S.FINISHED),
    ]
    p = compute_pipeline_progress(jobs, pipeline=_pl(PipelineStatus.RUNNING.value))
    assert p["done"] is False
    assert p["has_error"] is False


def test_pipeline_none_falls_back_to_legacy_job_derived():
    """Orphans never minted a Pipeline row — pipeline=None keeps the
    legacy oracle so the badge still works for them."""
    jobs = [_parent(S.FINISHED, recalc_chained=0)]
    p = compute_pipeline_progress(jobs, pipeline=None)
    # phase 2 vacuously satisfied (0 expected); phase 3 satisfied (no aggs).
    assert p["done"] is True
    assert p["has_error"] is False


def test_pipeline_phase_still_job_derived_when_row_passed():
    """``phase`` is UX granularity, not bound to ``pipelines.status`` —
    even when the table says RUNNING, ``phase`` reflects which step is
    actually mid-flight per the jobs."""
    jobs = [
        _parent(S.FINISHED, recalc_chained=2),
        _recalc(2, S.FINISHED, agg_id=10),
        _recalc(3, S.RUNNING),
    ]
    p = compute_pipeline_progress(jobs, pipeline=_pl(PipelineStatus.RUNNING.value))
    assert p["phase"] == 2  # parent done, recalc fan-out still in flight
    assert p["done"] is False
