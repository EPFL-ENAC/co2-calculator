from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audit import AuditDocument, SyncStatusEnum
from app.services.audit_sync_service import AuditSyncService


# Fixtures
@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.exec = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_es_client():
    """Create a mock Elasticsearch client."""
    es_instance = MagicMock()
    es_instance.sync_audit_record = MagicMock(return_value=True)
    es_instance.bulk_sync_audit_records = MagicMock(
        return_value={"success": [], "errors": []}
    )
    return es_instance


@pytest.fixture
def audit_sync_service(mock_session, mock_es_client):
    """Create an AuditSyncService instance with mocked dependencies."""
    # Patch the ElasticsearchClient to avoid initialization issues
    with patch(
        "app.services.audit_sync_service.ElasticsearchClient"
    ) as mock_es_constructor:
        mock_es_constructor.return_value = mock_es_client
        # Create the service with the mock session
        service = AuditSyncService(mock_session)
        # Replace the ES client with our mock
        service.es_client = mock_es_client
        return service


@pytest.fixture
def sample_audit_record():
    """Create a sample audit record for testing."""
    return AuditDocument(
        id=1,
        entity_type="test_entity",
        entity_id=123,
        version=1,
        is_current=True,
        data_snapshot={},
        change_type="CREATE",
        changed_by=1,
        changed_at=datetime.utcnow(),
        handler_id="test_handler",
        handled_ids=[],
        ip_address="127.0.0.1",
        route_path="/test",
        route_payload={},
        current_hash="test_hash",
        sync_status=SyncStatusEnum.PENDING,
        sync_error=None,
        synced_at=None,
    )


# Tests
class TestAuditSyncService:
    """Test suite for AuditSyncService."""

    # Tests for sync_single_audit_record
    async def test_sync_single_audit_record_success(
        self, audit_sync_service, mock_session, sample_audit_record
    ):
        """Test successful sync of a single audit record."""
        # Setup
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_audit_record)
        audit_sync_service.repo = mock_repo

        audit_sync_service.es_client.sync_audit_record.return_value = True

        # Execute
        result = await audit_sync_service.sync_single_audit_record(1)

        # Assert
        assert result is True
        assert sample_audit_record.sync_status == SyncStatusEnum.SYNCED
        assert sample_audit_record.synced_at is not None
        assert sample_audit_record.sync_error is None
        audit_sync_service.es_client.sync_audit_record.assert_called_once()
        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        mock_session.commit.assert_awaited()

    async def test_sync_single_audit_record_already_synced(
        self, audit_sync_service, mock_session, sample_audit_record
    ):
        """Test syncing a record that's already synced."""
        # Setup
        sample_audit_record.sync_status = SyncStatusEnum.SYNCED
        sample_audit_record.synced_at = datetime.utcnow()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_audit_record)
        audit_sync_service.repo = mock_repo

        # Execute
        result = await audit_sync_service.sync_single_audit_record(1)

        # Assert
        assert result is True
        assert sample_audit_record.sync_status == SyncStatusEnum.SYNCED
        assert sample_audit_record.synced_at is not None
        # Should not call ES client for already synced records
        audit_sync_service.es_client.sync_audit_record.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()
        mock_session.commit.assert_not_called()

    async def test_sync_single_audit_record_already_failed(
        self, audit_sync_service, mock_session, sample_audit_record
    ):
        """Test syncing a record that has already failed."""
        # Setup
        sample_audit_record.sync_status = SyncStatusEnum.FAILED
        sample_audit_record.sync_error = "Previous error"

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_audit_record)
        audit_sync_service.repo = mock_repo

        # Execute
        result = await audit_sync_service.sync_single_audit_record(1)

        # Assert
        assert result is False
        assert sample_audit_record.sync_status == SyncStatusEnum.FAILED
        # Should not call ES client for already failed records
        audit_sync_service.es_client.sync_audit_record.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()
        mock_session.commit.assert_not_called()

    async def test_sync_single_audit_record_not_found(
        self, audit_sync_service, mock_session
    ):
        """Test syncing a record that doesn't exist."""
        # Setup
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        audit_sync_service.repo = mock_repo

        # Execute
        result = await audit_sync_service.sync_single_audit_record(999)

        # Assert
        assert result is False
        audit_sync_service.es_client.sync_audit_record.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()

    async def test_sync_single_audit_record_es_sync_failure(
        self, audit_sync_service, mock_session, sample_audit_record
    ):
        """Test when ES sync fails."""
        # Setup
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_audit_record)
        audit_sync_service.repo = mock_repo

        audit_sync_service.es_client.sync_audit_record.return_value = False

        # Execute
        result = await audit_sync_service.sync_single_audit_record(1)

        # Assert
        assert result is False
        assert sample_audit_record.sync_status == SyncStatusEnum.FAILED
        assert sample_audit_record.sync_error == "Failed to sync to Elasticsearch"
        audit_sync_service.es_client.sync_audit_record.assert_called_once()
        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        mock_session.commit.assert_awaited()

    async def test_sync_single_audit_record_exception_during_sync(
        self, audit_sync_service, mock_session, sample_audit_record
    ):
        """Test when an exception occurs during sync."""
        # Setup
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_audit_record)
        audit_sync_service.repo = mock_repo

        audit_sync_service.es_client.sync_audit_record.side_effect = Exception(
            "Test error"
        )

        # Execute
        result = await audit_sync_service.sync_single_audit_record(1)

        # Assert
        assert result is False
        assert sample_audit_record.sync_status == SyncStatusEnum.FAILED
        assert sample_audit_record.sync_error == "Test error"
        audit_sync_service.es_client.sync_audit_record.assert_called_once()
        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        mock_session.commit.assert_awaited()

    async def test_sync_single_audit_record_exception_during_status_update(
        self, audit_sync_service, mock_session, sample_audit_record
    ):
        """Test when an exception occurs during status update."""
        # Setup
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_audit_record)
        mock_repo.get_by_id.side_effect = [
            sample_audit_record,
            sample_audit_record,  # For the second call when updating status
        ]
        audit_sync_service.repo = mock_repo

        audit_sync_service.es_client.sync_audit_record.return_value = True
        # Simulate an exception during the first flush (syncing state)
        mock_session.flush.side_effect = Exception("Flush error")

        # Execute
        result = await audit_sync_service.sync_single_audit_record(1)

        # Assert
        assert result is False
        # ES client should not be called because the flush failed before ES call
        audit_sync_service.es_client.sync_audit_record.assert_not_called()
        # Should be called at least once for setting syncing state
        assert mock_session.add.call_count >= 1
        assert mock_session.flush.call_count >= 1
        # Commit should not be called because of the exception
        mock_session.commit.assert_not_called()

    # Tests for sync_pending_audit_records
    async def test_sync_pending_audit_records_success(
        self, audit_sync_service, mock_session
    ):
        """Test successful sync of pending audit records."""
        # Setup
        pending_records = []
        for i in range(3):
            record = AuditDocument(
                id=i + 1,
                entity_type="test_entity",
                entity_id=123 + i,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.PENDING,
                sync_error=None,
                synced_at=None,
            )
            pending_records.append(record)

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=pending_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock ES client response
        audit_sync_service.es_client.bulk_sync_audit_records.return_value = {
            "success": [{"id": 1}, {"id": 2}, {"id": 3}],
            "errors": [],
        }

        # Execute
        result = await audit_sync_service.sync_pending_audit_records(batch_size=100)

        # Assert
        assert result["synced"] == 3
        assert result["failed"] == 0
        assert result["total"] == 3
        audit_sync_service.es_client.bulk_sync_audit_records.assert_called_once()
        # Each record gets add() called twice: once for syncing state,
        # once for final state
        assert mock_session.add.call_count == 6
        mock_session.flush.assert_awaited()
        mock_session.commit.assert_awaited()

    async def test_sync_pending_audit_records_mixed_results(
        self, audit_sync_service, mock_session
    ):
        """Test sync with mixed success/failure results."""
        # Setup
        pending_records = []
        for i in range(3):
            record = AuditDocument(
                id=i + 1,
                entity_type="test_entity",
                entity_id=123 + i,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.PENDING,
                sync_error=None,
                synced_at=None,
            )
            pending_records.append(record)

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=pending_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock ES client response with mixed results
        audit_sync_service.es_client.bulk_sync_audit_records.return_value = {
            "success": [{"id": 1}, {"id": 3}],  # Records 1 and 3 succeed
            "errors": [{"id": 2}],  # Record 2 fails
        }

        # Execute
        result = await audit_sync_service.sync_pending_audit_records(batch_size=100)

        # Assert
        assert result["synced"] == 2
        assert result["failed"] == 1
        assert result["total"] == 3
        audit_sync_service.es_client.bulk_sync_audit_records.assert_called_once()
        # Each record gets add() called twice: once for syncing state,
        # once for final state
        assert mock_session.add.call_count == 6
        mock_session.flush.assert_awaited()

    async def test_sync_pending_audit_records_no_pending_records(
        self, audit_sync_service, mock_session
    ):
        """Test sync when no pending records exist."""
        # Setup
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Execute
        result = await audit_sync_service.sync_pending_audit_records(batch_size=100)

        # Assert
        assert result["synced"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0
        audit_sync_service.es_client.bulk_sync_audit_records.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()

    async def test_sync_pending_audit_records_es_bulk_failure(
        self, audit_sync_service, mock_session
    ):
        """Test when ES bulk sync fails."""
        # Setup
        pending_records = []
        for i in range(2):
            record = AuditDocument(
                id=i + 1,
                entity_type="test_entity",
                entity_id=123 + i,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.PENDING,
                sync_error=None,
                synced_at=None,
            )
            pending_records.append(record)

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=pending_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock ES client response with all failures
        audit_sync_service.es_client.bulk_sync_audit_records.return_value = {
            "success": [],
            "errors": [{"id": 1}, {"id": 2}],
        }

        # Execute
        result = await audit_sync_service.sync_pending_audit_records(batch_size=100)

        # Assert
        assert result["synced"] == 0
        assert result["failed"] == 2
        assert result["total"] == 2
        audit_sync_service.es_client.bulk_sync_audit_records.assert_called_once()
        # Each record gets add() called twice: once for syncing state,
        # once for final state
        assert mock_session.add.call_count == 4
        mock_session.flush.assert_awaited()

    async def test_sync_pending_audit_records_exception(
        self, audit_sync_service, mock_session
    ):
        """Test when an exception occurs during bulk sync."""
        # Setup
        mock_session.exec.side_effect = Exception("Database error")

        # Execute
        result = await audit_sync_service.sync_pending_audit_records(batch_size=100)

        # Assert
        assert result["synced"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0
        assert "error" in result
        audit_sync_service.es_client.bulk_sync_audit_records.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()

    # Tests for retry_failed_audit_records
    async def test_retry_failed_audit_records_success(
        self, audit_sync_service, mock_session
    ):
        """Test successful retry of failed audit records."""
        # Setup
        failed_records = []
        for i in range(2):
            record = AuditDocument(
                id=i + 1,
                entity_type="test_entity",
                entity_id=123 + i,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.FAILED,
                sync_error="Previous error",
                synced_at=None,
            )
            failed_records.append(record)

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=failed_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock the sync_single_audit_record method to return True
        with patch.object(
            audit_sync_service, "sync_single_audit_record", return_value=True
        ) as mock_sync:
            # Execute
            result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

            # Assert
            assert result["retried"] == 2
            assert result["success"] == 2
            assert result["failed"] == 0
            assert mock_sync.call_count == 2  # Called for each record
            mock_session.flush.assert_awaited()
            mock_session.commit.assert_awaited()

    async def test_retry_failed_audit_records_mixed_results(
        self, audit_sync_service, mock_session
    ):
        """Test retry with mixed success/failure results."""
        # Setup
        failed_records = []
        for i in range(3):
            record = AuditDocument(
                id=i + 1,
                entity_type="test_entity",
                entity_id=123 + i,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.FAILED,
                sync_error="Previous error",
                synced_at=None,
            )
            failed_records.append(record)

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=failed_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock the sync_single_audit_record method to return mixed results
        async def mock_sync_side_effect(audit_id):
            # First call succeeds, second fails, third succeeds
            if audit_id == 1:
                return True
            elif audit_id == 2:
                return False
            elif audit_id == 3:
                return True
            return False

        with patch.object(
            audit_sync_service,
            "sync_single_audit_record",
            side_effect=mock_sync_side_effect,
        ):
            # Execute
            result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

            # Assert
            assert result["retried"] == 3
            assert result["success"] == 2
            assert result["failed"] == 1
            mock_session.flush.assert_awaited()
            mock_session.commit.assert_awaited()

    async def test_retry_failed_audit_records_with_retry_limit_exceeded(
        self, audit_sync_service, mock_session
    ):
        """Test retry with records that have exceeded retry limit."""
        # Setup
        failed_records = [
            AuditDocument(
                id=1,
                entity_type="test_entity",
                entity_id=123,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.FAILED,
                sync_error="Retry limit exceeded",
                synced_at=None,
            )
        ]

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=failed_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Execute
        result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

        # Assert
        assert result["retried"] == 0
        assert result["success"] == 0
        assert result["failed"] == 1
        # Since no records were processed, flush and commit should not be called
        mock_session.flush.assert_not_awaited()
        mock_session.commit.assert_not_awaited()

    async def test_retry_failed_audit_records_with_missing_id(
        self, audit_sync_service, mock_session
    ):
        """Test retry with records that have missing IDs."""
        # Setup
        failed_records = [
            AuditDocument(
                id=None,  # Missing ID
                entity_type="test_entity",
                entity_id=123,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.FAILED,
                sync_error="Previous error",
                synced_at=None,
            )
        ]

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=failed_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Execute
        result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

        # Assert
        assert result["retried"] == 0
        assert result["success"] == 0
        assert result["failed"] == 1

    async def test_retry_failed_audit_records_with_empty_sync_error(
        self, audit_sync_service, mock_session
    ):
        """Test retry with records that have empty sync_error."""
        # Setup
        failed_records = [
            AuditDocument(
                id=1,
                entity_type="test_entity",
                entity_id=123,
                version=1,
                is_current=True,
                data_snapshot={},
                change_type="CREATE",
                changed_by=1,
                changed_at=datetime.utcnow(),
                handler_id="test_handler",
                handled_ids=[],
                ip_address="127.0.0.1",
                route_path="/test",
                route_payload={},
                current_hash="test_hash",
                sync_status=SyncStatusEnum.FAILED,
                sync_error=None,  # Empty sync_error
                synced_at=None,
            )
        ]

        # Mock the session execution
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=failed_records)
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock the sync_single_audit_record method to return False
        # (simulating retry failure)
        with patch.object(
            audit_sync_service, "sync_single_audit_record", return_value=False
        ) as mock_sync:
            # Execute
            result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

            # Assert
            assert result["retried"] == 1
            assert result["success"] == 0
            assert result["failed"] == 1

            # Verify that the sync_error was set to "Retry attempt failed"
            assert failed_records[0].sync_error == "Retry attempt failed"
            assert mock_sync.call_count == 1

    async def test_retry_failed_audit_records_no_failed_records(
        self, audit_sync_service, mock_session
    ):
        """Test retry when no failed records exist."""
        # Setup
        mock_result = AsyncMock()
        mock_result.all = MagicMock(return_value=[])
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Execute
        result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

        # Assert
        assert result["retried"] == 0
        assert result["success"] == 0
        assert result["failed"] == 0

    async def test_retry_failed_audit_records_exception(
        self, audit_sync_service, mock_session
    ):
        """Test when an exception occurs during retry."""
        # Setup
        mock_session.exec.side_effect = Exception("Database error")

        # Execute
        result = await audit_sync_service.retry_failed_audit_records(max_retries=3)

        # Assert
        assert result["retried"] == 0
        assert result["success"] == 0
        assert result["failed"] == 0
        assert "error" in result
