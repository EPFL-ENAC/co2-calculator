"""Integration tests for the Elasticsearch client using pytest-elasticsearch."""

import pytest

from app.elasticsearch.client import (
    ELASTICSEARCH_INDEX,
    ElasticsearchClient,
    map_to_opdo_schema,
)


class TestElasticsearchClientIntegration:
    """Integration tests for the ElasticsearchClient class."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, elasticsearch):
        """Setup and teardown for each test."""
        # Store the original client
        self.original_client = elasticsearch

        # Create index if it doesn't exist
        if not elasticsearch.indices.exists(index=ELASTICSEARCH_INDEX):
            elasticsearch.indices.create(index=ELASTICSEARCH_INDEX)

        yield

        # Clean up - delete all documents in the index after each test
        try:
            elasticsearch.delete_by_query(
                index=ELASTICSEARCH_INDEX,
                body={"query": {"match_all": {}}},
                refresh=True,
            )
        except Exception:
            pass  # Ignore errors during cleanup

    def test_map_to_opdo_schema_integration(self):
        """Test that map_to_opdo_schema produces valid documents for Elasticsearch."""
        # Sample audit record
        audit_record = {
            "id": "test-123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "192.168.1.1",
            "route_path": "/api/users",
            "route_payload": {"key": "value"},
            "change_reason": "User creation",
            "entity_type": "User",
            "entity_id": 456,
        }

        # Transform to OPDo schema
        opdo_document = map_to_opdo_schema(audit_record)

        # Verify structure
        assert "@timestamp" in opdo_document
        assert "handler_id" in opdo_document
        assert "handled_id" in opdo_document
        assert "crudt" in opdo_document
        assert "source" in opdo_document
        assert "payload" in opdo_document

        # Verify values
        assert opdo_document["handler_id"] == "handler-123"
        assert opdo_document["handled_id"] == "1,2,3"
        assert opdo_document["crudt"] == "C"
        assert opdo_document["source"] == "192.168.1.1"
        assert isinstance(opdo_document["payload"], str)

    def test_sync_audit_record_integration(self):
        """Test syncing a single audit record to Elasticsearch."""
        # Create our Elasticsearch client with the test client
        client = ElasticsearchClient(self.original_client)

        # Test audit record
        audit_record = {
            "id": "int-122",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-122",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "192.168.1.1",
            "route_payload": {"key": "value"},
        }

        # Sync the record
        result = client.sync_audit_record(audit_record)

        # Verify success
        assert result is True

    def test_bulk_sync_audit_records_integration(self):
        """Test bulk syncing multiple audit records to Elasticsearch."""
        # Create our Elasticsearch client with the test client
        client = ElasticsearchClient(self.original_client)

        # Test audit records
        audit_records = [
            {
                "id": "int-123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "int-124",
                "changed_at": "2024-10-10 11:35:05.123453",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "UPDATE",
                "ip_address": "192.168.1.2",
                "route_payload": {"key": "value2"},
            },
        ]

        # Bulk sync the records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify success
        assert result["success"] == 2
        assert result["failed"] == 0
        assert result["errors"] == []

    def test_sync_audit_record_with_validation_error_integration(self):
        """Test syncing an audit record with validation error."""
        # Create our Elasticsearch client with the test client
        client = ElasticsearchClient(self.original_client)

        # Test audit record with invalid IP
        audit_record = {
            "id": "int-invalid",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "invalid_ip",  # Invalid IP
            "route_payload": {"key": "value"},
        }

        # Sync the record - should fail validation
        result = client.sync_audit_record(audit_record)

        # Verify failure
        assert result is False

    def test_bulk_sync_with_mixed_validity_integration(self):
        """Test bulk syncing with mix of valid and invalid records."""
        # Create our Elasticsearch client with the test client
        client = ElasticsearchClient(self.original_client)

        # Test audit records - one valid, one invalid
        audit_records = [
            {
                "id": "int-valid",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "int-invalid",
                "changed_at": "2024-10-10 11:35:05.123456",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "UPDATE",
                "ip_address": "invalid_ip",  # Invalid IP
                "route_payload": {"key": "value2"},
            },
        ]

        # Bulk sync the records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify partial success
        assert result["success"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["id"] == "int-invalid"
