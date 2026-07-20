"""Regression: the create_job audit snapshot must be stdlib-JSON-safe.

``create_job`` stores ``job.model_dump(mode="json")`` in the audit
document's JSON column, which is serialized by the plain ``json.dumps``
configured in ``app.db``. When ``created_at`` gained an insert-time
default (2026-07-17), a python-mode ``model_dump()`` started carrying a
real ``datetime`` and every ``POST /v1/sync/dispatch`` 500'd on the
audit INSERT.
"""

import json

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)


def test_fresh_job_snapshot_is_json_serializable():
    job = DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        ingestion_method=IngestionMethod.csv,
        target_type=TargetType.DATA_ENTRIES,
        state=IngestionState.NOT_STARTED,
        status_message="Job created",
        meta={},
    )

    # created_at is stamped at construction — the exact condition that
    # broke the python-mode dump.
    assert job.created_at is not None

    snapshot = job.model_dump(mode="json")
    json.dumps(snapshot, ensure_ascii=False)
    assert isinstance(snapshot["created_at"], str)
