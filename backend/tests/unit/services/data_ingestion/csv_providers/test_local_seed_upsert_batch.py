"""Regression test for ``LocalFactorCSVProvider._upsert_batch``.

Plan 310B switched the production factor ingest from delete-and-insert
to ``ON CONFLICT DO UPDATE``, which requires a ``job_id`` to stamp on
``last_seen_job_id``.  Local seed scripts have no DataIngestionJob and
therefore no ``job_id``, so once a seed CSV exceeds BATCH_SIZE the
main batch loop would call ``_upsert_batch`` and crash with
``ValueError("job_id is required for factor upsert")``.

The fix overrides ``_upsert_batch`` on ``LocalFactorCSVProvider`` to
keep the legacy ``bulk_create`` path.  This test pins that contract.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_ingestion.csv_providers.local_seed import (
    LocalFactorCSVProvider,
)


@pytest.mark.asyncio
async def test_local_factor_provider_upsert_batch_uses_legacy_bulk_create():
    """``LocalFactorCSVProvider._upsert_batch`` must NOT raise the
    "job_id is required" ValueError that the base class enforces.
    Instead it routes the batch through ``_process_batch`` (which calls
    ``factor_service.bulk_create``) so seed scripts can ingest factors
    without a tracked DataIngestionJob.
    """
    provider = LocalFactorCSVProvider(
        config={
            "local_file_path": "/tmp/test.csv",
            "module_type_id": 1,
            "data_entry_type_id": 1,
            "year": 2025,
        },
        data_session=MagicMock(),
    )
    # No set_job_id call — self.job_id stays None, the exact state that
    # would crash the base-class _upsert_batch.
    assert provider.job_id is None

    factor_repo = MagicMock()
    # If _upsert_batch falls through to the base implementation, it
    # would call factor_repo.upsert_factors and raise on the missing
    # job_id.  We assert the legacy path is taken instead.
    factor_repo.upsert_factors = AsyncMock(
        side_effect=AssertionError(
            "Local seed must NOT call factor_repo.upsert_factors — "
            "no job_id available, would raise ValueError"
        )
    )

    batch = [MagicMock(), MagicMock(), MagicMock()]

    # Patch _process_batch to confirm the legacy path runs without
    # depending on FactorService internals.
    with patch.object(
        provider, "_process_batch", new_callable=AsyncMock
    ) as mock_process:
        reported = await provider._upsert_batch(batch, factor_repo)

    # Legacy path was taken — exactly one call with the same batch.
    mock_process.assert_awaited_once()
    assert mock_process.await_args.args[0] is batch
    # Reported count matches input length (no rowcount feedback in the
    # bulk_create path, so the override returns len(batch)).
    assert reported == 3
    # The base-class ValueError sentinel was never tripped.
    factor_repo.upsert_factors.assert_not_awaited()
