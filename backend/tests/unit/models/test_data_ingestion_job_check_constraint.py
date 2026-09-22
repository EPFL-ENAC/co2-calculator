"""#2904 — the unit-specific entity_id check must reach the model metadata.

``DataIngestionJob`` declared ``__table_args__`` twice; the second silently
replaced the first, so the check lived only in migration ``3ccb48f25866``
and the #2904 collapse would have dropped it.
"""

from app.models.data_ingestion import DataIngestionJob


def test_unit_specific_entity_id_check_is_declared():
    names = {c.name for c in DataIngestionJob.__table__.constraints}

    assert "ck_data_ingestion_jobs_unit_specific_has_entity_id" in names
