"""Pipeline-ops-console meta allow-list (#1234).

The list endpoint must never ship the KB-scale ``error_details`` /
``affected_module_ids`` arrays — only the five keys that thread the DAG
and show provenance.  This locks that contract.
"""

import pytest
from fastapi import HTTPException

from app.api.v1.data_sync import (
    _PIPELINE_META_ALLOW,
    _project_pipeline_meta,
    _resolve_enum_name,
)
from app.models.data_ingestion import IngestionResult, IngestionState, PipelineStatus


def test_project_strips_big_arrays_keeps_allow_list():
    meta = {
        # Phase 5B (#1236) — these three meta keys were retired; the
        # allow-list must NOT carry them, and a legacy pipeline that
        # still has them on its meta gets them stripped.
        "parent_job_id": 9,
        "recalc_jobs_chained": 3,
        "aggregation_job_id": 14,
        "provider_name": "ModulePerYearCSVProvider",
        "filters": {},
        # #2A/#2B — bounded timeline + checklist included in the list view.
        "status_history": [{"message": "x", "ts": "2026-05-20T00:00:00+00:00"}],
        "phases": [{"name": "fetch_units", "state": "finished"}],
        # Must be dropped — these are the multi-KB offenders.
        "error_details": [{"data_entry_id": i, "error": "x" * 200} for i in range(50)],
        "affected_module_ids": list(range(2231)),
        "recalculation": {"recalculated": 15820},
        "config": {"file_path": "tmp/secret.csv"},
    }

    projected = _project_pipeline_meta(meta)

    assert set(projected) == set(_PIPELINE_META_ALLOW)
    assert "error_details" not in projected
    assert "affected_module_ids" not in projected
    # Retired keys MUST NOT be projected even if legacy meta carries them.
    assert "parent_job_id" not in projected
    assert "recalc_jobs_chained" not in projected
    assert "aggregation_job_id" not in projected
    assert projected["status_history"] == meta["status_history"]
    assert projected["phases"] == meta["phases"]


def test_project_handles_none_and_partial_meta():
    assert _project_pipeline_meta(None) == {}
    assert _project_pipeline_meta({}) == {}
    # ``parent_job_id`` retired post-5B → stripped; ``x`` not in
    # allow-list → also stripped; result is empty.
    assert _project_pipeline_meta({"parent_job_id": 1, "x": 2}) == {}


# ---------------------------------------------------------------------------
# _resolve_enum_name (#1234) — int-enum filter params must accept the NAME.
# ---------------------------------------------------------------------------


def test_resolve_enum_name_accepts_case_insensitive_name():
    assert _resolve_enum_name(IngestionState, "RUNNING", "state") is (
        IngestionState.RUNNING
    )
    assert _resolve_enum_name(IngestionState, "not_started", "state") is (
        IngestionState.NOT_STARTED
    )
    assert _resolve_enum_name(IngestionResult, "Error", "result") is (
        IngestionResult.ERROR
    )


def test_resolve_enum_name_none_passes_through():
    assert _resolve_enum_name(IngestionState, None, "state") is None


def test_resolve_enum_name_rejects_unknown_with_422():
    with pytest.raises(HTTPException) as exc:
        _resolve_enum_name(IngestionState, "BOGUS", "state")
    assert exc.value.status_code == 422
    # The integer value must NOT be accepted — names only (this is the
    # exact 422 the user hit with ?state=NOT_STARTED on the int enum).
    with pytest.raises(HTTPException):
        _resolve_enum_name(IngestionState, "0", "state")


# ---------------------------------------------------------------------------
# Phase 3 read-flip (#1236) — ``?state=`` resolves to ``PipelineStatus``.
# ---------------------------------------------------------------------------


def test_resolve_enum_name_accepts_pipeline_status():
    """``state`` URL param now means PipelineStatus (#1236 Phase 3).

    The 5 values (NOT_STARTED / RUNNING / SUCCESS / PARTIAL / FAILED)
    must all resolve case-insensitively.
    """
    assert _resolve_enum_name(PipelineStatus, "RUNNING", "state") is (
        PipelineStatus.RUNNING
    )
    assert _resolve_enum_name(PipelineStatus, "partial", "state") is (
        PipelineStatus.PARTIAL
    )
    assert _resolve_enum_name(PipelineStatus, "Failed", "state") is (
        PipelineStatus.FAILED
    )
