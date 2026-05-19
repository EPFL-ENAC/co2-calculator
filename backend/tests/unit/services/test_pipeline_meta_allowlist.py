"""Pipeline-ops-console meta allow-list (#1234).

The list endpoint must never ship the KB-scale ``error_details`` /
``affected_module_ids`` arrays — only the five keys that thread the DAG
and show provenance.  This locks that contract.
"""

from app.api.v1.data_sync import _PIPELINE_META_ALLOW, _project_pipeline_meta


def test_project_strips_big_arrays_keeps_allow_list():
    meta = {
        "parent_job_id": 9,
        "recalc_jobs_chained": 3,
        "aggregation_job_id": 14,
        "provider_name": "ModulePerYearCSVProvider",
        "filters": {},
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
    assert projected["aggregation_job_id"] == 14


def test_project_handles_none_and_partial_meta():
    assert _project_pipeline_meta(None) == {}
    assert _project_pipeline_meta({}) == {}
    assert _project_pipeline_meta({"parent_job_id": 1, "x": 2}) == {"parent_job_id": 1}
