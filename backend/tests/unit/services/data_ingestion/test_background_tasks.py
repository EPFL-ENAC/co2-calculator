from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import IngestionStatus
from app.tasks.ingestion_tasks import run_sync_task


@pytest.mark.asyncio
async def test_run_sync_task_success():
    fake_job = MagicMock()
    fake_job.status_code = IngestionStatus.PENDING
    fake_job.id = 123
    fake_job.user = None
    fake_job.meta = None

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "success",
            "status_code": 200,
            "data": {"foo": "bar"},
        }
    )
    fake_provider._update_job = AsyncMock()

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch("app.tasks.ingestion_tasks.SessionLocal") as mock_session_local,
        patch("app.tasks.ingestion_tasks.DataIngestionRepository") as mock_repo,
        patch(
            "app.tasks.ingestion_tasks.ProviderFactory.get_provider_class",
            return_value=FakeProviderClass,
        ),
    ):
        # Create mock sessions with async methods
        mock_job_session = MagicMock()
        mock_job_session.commit = AsyncMock()
        mock_job_session.rollback = AsyncMock()

        mock_data_session = MagicMock()
        mock_data_session.commit = AsyncMock()
        mock_data_session.rollback = AsyncMock()

        # Configure SessionLocal to return different sessions for each call
        mock_session_local.return_value.__aenter__ = AsyncMock(
            side_effect=[mock_job_session, mock_data_session]
        )
        mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_repo.return_value.get_job_by_id = AsyncMock(return_value=fake_job)

        await run_sync_task("FakeProviderClass", job_id=123, filters={"foo": "bar"})

        fake_provider.set_job_id.assert_awaited_once_with(123)
        fake_provider.ingest.assert_awaited_once()
        fake_provider._update_job.assert_awaited()
        # Verify data session was committed
        mock_data_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_sync_task_job_not_found():
    with (
        patch("app.tasks.ingestion_tasks.SessionLocal") as mock_session_local,
        patch("app.tasks.ingestion_tasks.DataIngestionRepository") as mock_repo,
        patch(
            "app.tasks.ingestion_tasks.ProviderFactory.get_provider_class",
            return_value=None,
        ),
    ):
        # Create mock sessions with async methods
        mock_job_session = MagicMock()
        mock_job_session.commit = AsyncMock()
        mock_job_session.rollback = AsyncMock()

        mock_data_session = MagicMock()
        mock_data_session.commit = AsyncMock()
        mock_data_session.rollback = AsyncMock()

        mock_session_local.return_value.__aenter__ = AsyncMock(
            side_effect=[mock_job_session, mock_data_session]
        )
        mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_repo.return_value.get_job_by_id = AsyncMock(return_value=None)

        # Should not raise
        await run_sync_task("FakeProviderClass", job_id=999)
