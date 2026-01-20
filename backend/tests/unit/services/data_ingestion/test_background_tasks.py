from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_ingestion.background_tasks import run_sync_task


@pytest.mark.asyncio
async def test_run_sync_task_success():
    fake_job = MagicMock()
    fake_provider = MagicMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status": "success",
            "status_code": 200,
            "message": "ok",
            "data": {"foo": "bar"},
        }
    )
    fake_provider._update_job = AsyncMock()

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch(
            "app.services.data_ingestion.background_tasks.SessionLocal"
        ) as mock_session_local,
        patch(
            "app.services.data_ingestion.background_tasks.DataIngestionRepository"
        ) as mock_repo,
    ):
        mock_db = MagicMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_repo.return_value.get_job_by_id.return_value = fake_job

        await run_sync_task(FakeProviderClass, job_id=123, filters={"foo": "bar"})

        fake_provider.ingest.assert_awaited_once()
        fake_provider._update_job.assert_awaited()


@pytest.mark.asyncio
async def test_run_sync_task_job_not_found():
    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return MagicMock()

    with (
        patch(
            "app.services.data_ingestion.background_tasks.SessionLocal"
        ) as mock_session_local,
        patch(
            "app.services.data_ingestion.background_tasks.DataIngestionRepository"
        ) as mock_repo,
    ):
        mock_db = MagicMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_repo.return_value.get_job_by_id.return_value = None

        # Should not raise
        await run_sync_task(FakeProviderClass, job_id=999)
