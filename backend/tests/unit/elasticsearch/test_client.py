"""Unit tests for the Elasticsearch client."""

from unittest.mock import Mock, patch

import pytest

from app.elasticsearch.client import (
    ElasticsearchClient,
    format_timestamp,
    map_to_opdo_schema,
    resolve_handled_id,
    stringify_payload,
    validate_ip,
)


class TestFormatTimestamp:
    """Tests for the format_timestamp function."""

    def test_format_timestamp_valid(self):
        """Test formatting a valid timestamp string."""
        timestamp_str = "2024-10-10 11:34:05.123456"
        result = format_timestamp(timestamp_str)
        # Should be ISO formatted with Europe/Zurich timezone
        expected = "2024-10-10T11:34:05.123456+02:00"
        assert result == expected

    def test_format_timestamp_microseconds(self):
        """Test formatting timestamp with microseconds."""
        timestamp_str = "2024-01-01 00:00:00.000000"
        result = format_timestamp(timestamp_str)
        expected = "2024-01-01T00:00:00+01:00"  # +01:00 for winter time in Zurich
        assert result == expected


class TestValidateIp:
    """Tests for the validate_ip function."""

    def test_validate_ip_valid_ipv4(self):
        """Test validating a valid IPv4 address."""
        ip = "192.168.1.1"
        result = validate_ip(ip)
        assert result == ip

    def test_validate_ip_valid_ipv6(self):
        """Test validating a valid IPv6 address."""
        ip = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        result = validate_ip(ip)
        assert result == ip

    def test_validate_ip_invalid(self):
        """Test validating an invalid IP address."""
        ip = "invalid_ip"
        with pytest.raises(ValueError, match=f"Invalid IP for OPDo: {ip}"):
            validate_ip(ip)

    def test_validate_ip_localhost(self):
        """Test validating localhost IP."""
        ip = "127.0.0.1"
        result = validate_ip(ip)
        assert result == ip

    # Handle "unknown" IP addresses by using a placeholder
    def test_validate_ip_not_valid(self):
        ip = "unknown_not_valid"
        with pytest.raises(ValueError, match=f"Invalid IP for OPDo: {ip}"):
            validate_ip(ip)

    def test_validate_ip_unknown(self):
        """Test that 'unknown' is rejected as invalid."""
        ip = "unknown"
        with pytest.raises(ValueError, match="IP address cannot be 'unknown'"):
            validate_ip(ip)


class TestResolveHandledId:
    """Tests for the resolve_handled_id function."""

    def test_resolve_handled_id_with_handled_ids(self):
        """Test resolving handled_id when handled_ids is present."""
        audit_record = {"handled_ids": [1, 2, 3], "handler_id": "handler-123"}
        result = resolve_handled_id(audit_record)
        assert result == "1,2,3"

    def test_resolve_handled_id_with_empty_handled_ids(self):
        """Test resolving handled_id when handled_ids is empty but handler_id
        is present."""
        audit_record = {"handled_ids": [], "handler_id": "handler-123"}
        result = resolve_handled_id(audit_record)
        assert result == "handler-123"

    def test_resolve_handled_id_with_none_handled_ids(self):
        """Test resolving handled_id when handled_ids is None but handler_id
        is present."""
        audit_record = {"handled_ids": None, "handler_id": "handler-123"}
        result = resolve_handled_id(audit_record)
        assert result == "handler-123"

    def test_resolve_handled_id_no_handled_ids_no_handler_id(self):
        """Test that ValueError is raised when neither handled_ids nor handler_id
        is available."""
        audit_record = {"handled_ids": [], "handler_id": None}
        with pytest.raises(
            ValueError, match="OPDo violation: handled_id cannot be null"
        ):
            resolve_handled_id(audit_record)

    def test_resolve_handled_id_with_string_handled_ids(self):
        """Test resolving handled_id when handled_ids contains strings."""
        audit_record = {"handled_ids": ["a", "b", "c"], "handler_id": "handler-123"}
        result = resolve_handled_id(audit_record)
        assert result == "a,b,c"


class TestStringifyPayload:
    """Tests for the stringify_payload function."""

    def test_stringify_payload_string(self):
        """Test stringify_payload with string input."""
        payload = "test payload"
        result = stringify_payload(payload)
        assert result == payload

    def test_stringify_payload_dict(self):
        """Test stringify_payload with dict input."""
        payload = {"key": "value", "number": 123}
        result = stringify_payload(payload)
        # Should be compact JSON without spaces
        expected = '{"key":"value","number":123}'
        assert result == expected

    def test_stringify_payload_nested_dict(self):
        """Test stringify_payload with nested dict."""
        payload = {"outer": {"inner": "value"}, "array": [1, 2, 3]}
        result = stringify_payload(payload)
        expected = '{"outer":{"inner":"value"},"array":[1,2,3]}'
        assert result == expected


class TestMapToOpdoSchema:
    """Tests for the map_to_opdo_schema function."""

    def test_map_to_opdo_schema_valid_record(self):
        """Test mapping a valid audit record to OPDo schema."""
        audit_record = {
            "id": "123",
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

        result = map_to_opdo_schema(audit_record)

        expected = {
            "@timestamp": "2024-10-10T11:34:05.123456+02:00",
            "handler_id": "handler-123",
            "handled_id": "1,2,3",
            "crudt": "C",
            "source": "192.168.1.1",
            "payload": (
                '{"route_path":"/api/users","route_payload":{"key":"value"},'
                '"change_reason":"User creation","entity_type":"User",'
                '"entity_id":456}'
            ),
        }

        assert result == expected

    def test_map_to_opdo_schema_with_null_handler_id(self):
        """Test mapping when handler_id is None."""
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": None,
            "handled_ids": [1, 2, 3],
            "change_type": "UPDATE",
            "ip_address": "192.168.1.1",
            "route_path": "/api/users/123",
            "route_payload": "string payload",
            "change_reason": "User update",
            "entity_type": "User",
            "entity_id": 123,
        }

        result = map_to_opdo_schema(audit_record)

        expected = {
            "@timestamp": "2024-10-10T11:34:05.123456+02:00",
            "handler_id": None,
            "handled_id": "1,2,3",
            "crudt": "U",
            "source": "192.168.1.1",
            "payload": (
                '{"route_path":"/api/users/123","route_payload":"string '
                'payload","change_reason":"User update","entity_type":"User",'
                '"entity_id":123}'
            ),
        }

        assert result == expected

    def test_map_to_opdo_schema_implicit_handled_id(self):
        """Test mapping when handled_ids is empty and handler_id
        is used as implicit handled_id."""
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [],
            "change_type": "DELETE",
            "ip_address": "192.168.1.1",
            "route_path": "/api/users/123",
            "route_payload": {"key": "value"},
            "change_reason": "User deletion",
            "entity_type": "User",
            "entity_id": 123,
        }

        result = map_to_opdo_schema(audit_record)

        expected = {
            "@timestamp": "2024-10-10T11:34:05.123456+02:00",
            "handler_id": "handler-123",
            "handled_id": "handler-123",  # Implicit from handler_id
            "crudt": "D",
            "source": "192.168.1.1",
            "payload": (
                '{"route_path":"/api/users/123","route_payload":{"key":"value"},'
                '"change_reason":"User deletion","entity_type":"User",'
                '"entity_id":123}'
            ),
        }

        assert result == expected

    def test_map_to_opdo_schema_invalid_ip(self):
        """Test that ValueError is raised for invalid IP."""
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "invalid_ip",
            "route_path": "/api/users",
            "route_payload": {"key": "value"},
            "change_reason": "User creation",
            "entity_type": "User",
            "entity_id": 456,
        }

        with pytest.raises(ValueError, match="Invalid IP for OPDo: invalid_ip"):
            map_to_opdo_schema(audit_record)

    def test_map_to_opdo_schema_missing_handled_id(self):
        """Test that ValueError is raised when neither handled_ids nor
        handler_id is available."""
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": None,
            "handled_ids": [],
            "change_type": "CREATE",
            "ip_address": "192.168.1.1",
            "route_path": "/api/users",
            "route_payload": {"key": "value"},
            "change_reason": "User creation",
            "entity_type": "User",
            "entity_id": 456,
        }

        with pytest.raises(
            ValueError, match="OPDo violation: handled_id cannot be null"
        ):
            map_to_opdo_schema(audit_record)


class TestElasticsearchClient:
    """Tests for the ElasticsearchClient class."""

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_initialize_client_success(self, mock_elasticsearch, mock_path, caplog):
        """Test successful initialization of Elasticsearch client."""
        import logging

        # Set up caplog to capture INFO level logs
        caplog.set_level(logging.INFO)

        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Create the client
        client = ElasticsearchClient()

        # Verify the client was initialized
        assert client.client == mock_es_instance
        mock_elasticsearch.assert_called_once()
        mock_es_instance.info.assert_called_once()

        # Verify that info was logged with the specific message
        assert "Successfully connected to Elasticsearch" in caplog.text

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.logger")
    def test_initialize_client_certificate_not_found(self, mock_logger, mock_path):
        """Test initialization fails when certificate is not found."""
        # Mock the Path.exists() to return False
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = False

        # Create the client and expect FileNotFoundError
        with pytest.raises(FileNotFoundError) as exc_info:
            ElasticsearchClient()

        # Verify the error message and logging
        assert "Elasticsearch CA certificate not found at" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_initialize_client_connection_error(self, mock_elasticsearch, mock_path):
        """Test initialization fails when connection to Elasticsearch fails."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client to raise ConnectionError
        mock_elasticsearch.side_effect = ConnectionError("Connection failed")

        # Create the client and expect ConnectionError
        with pytest.raises(ConnectionError):
            ElasticsearchClient()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("app.elasticsearch.client.logger")
    def test_initialize_client_authentication_error(
        self, mock_logger, mock_elasticsearch, mock_path
    ):
        """Test initialization fails when authentication with Elasticsearch fails."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client to raise AuthenticationException
        # Create a proper mock that simulates the AuthenticationException
        mock_elasticsearch.side_effect = Exception("Authentication failed")

        # Create the client and expect Exception (since we're mocking)
        with pytest.raises(Exception):
            ElasticsearchClient()

        # Verify that error was logged
        mock_logger.error.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_initialize_client_unexpected_error(self, mock_elasticsearch, mock_path):
        """Test initialization fails when unexpected error occurs."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client to raise unexpected Exception
        mock_elasticsearch.side_effect = Exception("Unexpected error")

        # Create the client and expect Exception
        with pytest.raises(Exception):
            ElasticsearchClient()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_sync_audit_record_success(self, mock_elasticsearch, mock_path):
        """Test successful sync of audit record."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Create the client
        client = ElasticsearchClient()

        # Test audit record
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "192.168.1.1",
            "route_payload": {"key": "value"},
        }

        # Call sync_audit_record
        result = client.sync_audit_record(audit_record)

        # Verify success
        assert result is True
        mock_es_instance.index.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_sync_audit_record_invalid_data(self, mock_elasticsearch, mock_path):
        """Test sync_audit_record with invalid data."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Create the client
        client = ElasticsearchClient()

        # Test audit record with invalid IP
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "invalid_ip",
            "route_payload": {"key": "value"},
        }

        # Call sync_audit_record
        result = client.sync_audit_record(audit_record)

        # Verify failure
        assert result is False
        mock_es_instance.index.assert_not_called()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_sync_audit_record_elasticsearch_exception(
        self, mock_elasticsearch, mock_path
    ):
        """Test sync_audit_record when Elasticsearch throws an exception."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}
        # Mock the index method to throw an exception
        mock_es_instance.index.side_effect = Exception("Connection failed")

        # Create the client
        client = ElasticsearchClient()

        # Test audit record
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "192.168.1.1",
            "route_payload": {"key": "value"},
        }

        # Call sync_audit_record
        result = client.sync_audit_record(audit_record)

        # Verify failure
        assert result is False

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_sync_audit_record_client_not_initialized(
        self, mock_elasticsearch, mock_path
    ):
        """Test sync_audit_record when client is not initialized."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_elasticsearch.return_value = Mock()

        # Create the client
        client = ElasticsearchClient()
        # Manually set client to None to simulate initialization failure
        client.client = None

        # Test audit record
        audit_record = {
            "id": "123",
            "changed_at": "2024-10-10 11:34:05.123456",
            "handler_id": "handler-123",
            "handled_ids": [1, 2, 3],
            "change_type": "CREATE",
            "ip_address": "192.168.1.1",
            "route_payload": {"key": "value"},
        }

        # Call sync_audit_record
        result = client.sync_audit_record(audit_record)

        # Verify failure
        assert result is False

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    def test_bulk_sync_audit_records_success(
        self, mock_bulk, mock_elasticsearch, mock_path
    ):
        """Test successful bulk sync of audit records."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock the bulk operation
        mock_bulk.return_value = (2, [])  # 2 successes, 0 failures

        # Create the client
        client = ElasticsearchClient()

        # Test audit records
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "124",
                "changed_at": "2024-10-10 11:35:05.123456",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "UPDATE",
                "ip_address": "192.168.1.2",
                "route_payload": {"key": "value2"},
            },
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify success
        assert result["success"] == 2
        assert result["failed"] == 0
        assert result["errors"] == []
        mock_bulk.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    @patch("app.elasticsearch.client.logger")
    def test_bulk_sync_audit_records_with_validation_errors(
        self, mock_logger, mock_bulk, mock_elasticsearch, mock_path
    ):
        """Test bulk sync with validation errors."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock the bulk operation
        mock_bulk.return_value = (1, [])  # 1 success, 0 failures

        # Create the client
        client = ElasticsearchClient()

        # Test audit records - one valid, one invalid
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "124",
                "changed_at": "2024-10-10 11:35:05.123456",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "UPDATE",
                "ip_address": "invalid_ip",  # Invalid IP
                "route_payload": {"key": "value2"},
            },
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify partial success
        assert result["success"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["id"] == "124"
        mock_bulk.assert_called_once()
        # Verify that error was logged
        mock_logger.error.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("app.elasticsearch.client.map_to_opdo_schema")
    @patch("app.elasticsearch.client.logger")
    @patch("elasticsearch.helpers.bulk")
    def test_bulk_sync_audit_records_general_exception_in_processing(
        self,
        mock_bulk,
        mock_logger,
        mock_map_to_opdo_schema,
        mock_elasticsearch,
        mock_path,
    ):
        """Test bulk sync when general exception occurs during record processing."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock map_to_opdo_schema to process first record successfully
        # and fail on second
        def map_to_opdo_schema_side_effect(record):
            if record["id"] == "123":
                # Process first record successfully
                return {
                    "@timestamp": "2024-10-10T11:34:05.123456+02:00",
                    "handler_id": "handler-123",
                    "handled_id": "1,2,3",
                    "crudt": "C",
                    "source": "192.168.1.1",
                    "payload": '{"route_payload":{"key":"value"}}',
                }
            else:
                # Raise exception for second record
                raise Exception("Processing failed")

        mock_map_to_opdo_schema.side_effect = map_to_opdo_schema_side_effect

        # Mock the bulk operation to return 1 success
        mock_bulk.return_value = (1, [])  # 1 success, 0 failures

        # Create the client
        client = ElasticsearchClient()

        # Test audit records - one valid, one that causes exception
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "124",
                "changed_at": "2024-10-10 11:35:05.123456",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "UPDATE",
                "ip_address": "192.168.1.2",
                "route_payload": {"key": "value2"},
            },
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify partial success
        assert result["success"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["id"] == "124"
        # Verify that error was logged
        mock_logger.error.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    def test_bulk_sync_audit_records_all_invalid(
        self, mock_bulk, mock_elasticsearch, mock_path, caplog
    ):
        """Test bulk sync when all records are invalid."""
        import logging

        # Set up caplog to capture INFO level logs
        caplog.set_level(logging.INFO)

        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_elasticsearch.return_value = Mock()

        # Create the client
        client = ElasticsearchClient()

        # Test audit records - all invalid
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": None,
                "handled_ids": [],  # No handled_ids and no handler_id
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            }
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify no success
        assert result["success"] == 0
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        mock_bulk.assert_not_called()

        # Verify that info was logged with the specific message
        assert "No valid audit records to sync after validation" in caplog.text

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    def test_bulk_sync_audit_records_client_not_initialized(
        self, mock_elasticsearch, mock_path
    ):
        """Test bulk_sync_audit_records when client is not initialized."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_elasticsearch.return_value = Mock()

        # Create the client
        client = ElasticsearchClient()
        # Manually set client to None to simulate initialization failure
        client.client = None

        # Test audit records
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            }
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify failure
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result["errors"] == []

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    @patch("app.elasticsearch.client.logger")
    def test_bulk_sync_audit_records_bulk_exception(
        self, mock_logger, mock_bulk, mock_elasticsearch, mock_path
    ):
        """Test bulk_sync_audit_records when bulk operation throws an exception."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock the bulk operation to throw an exception
        mock_bulk.side_effect = Exception("Bulk operation failed")

        # Create the client
        client = ElasticsearchClient()

        # Test audit records
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            }
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify failure
        assert result["success"] == 0
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        mock_logger.error.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    @patch("app.elasticsearch.client.logger")
    def test_bulk_sync_audit_records_general_exception(
        self, mock_logger, mock_bulk, mock_elasticsearch, mock_path
    ):
        """Test bulk_sync_audit_records when a general exception occurs."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock the bulk function to raise an exception
        # that will be caught by the outer try-except
        # We need to make sure this exception isn't caught
        # by the inner try-except blocks
        # One way to do this is to have the exception
        # occur after the actions have been prepared
        mock_bulk.side_effect = Exception("General exception in bulk operation")

        # Create the client
        client = ElasticsearchClient()

        # Test audit records
        audit_records = [
            {
                "id": "123",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            }
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify failure - the outer exception handler should catch this
        assert result["success"] == 0
        assert result["failed"] == 1  # Length of audit_records
        assert len(result["errors"]) == 1
        assert result["errors"][0] == "General exception in bulk operation"
        # Verify that error was logged
        mock_logger.error.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    def test_bulk_sync_audit_records_with_version_conflicts(
        self, mock_bulk, mock_elasticsearch, mock_path
    ):
        """Test bulk_sync_audit_records with version conflict errors."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock the bulk operation to return success count and failed items
        # with version conflicts
        mock_bulk.return_value = (
            1,  # 1 success
            [  # Failed items list with version conflict
                {
                    "create": {
                        "_index": "test-index",
                        "_id": "conflict-id",
                        "status": 409,
                        "error": {
                            "type": "version_conflict_engine_exception",
                            "reason": (
                                "[conflict-id]: version conflict, document"
                                " already exists (current version [1])"
                            ),
                        },
                    }
                }
            ],
        )

        # Create the client
        client = ElasticsearchClient()

        # Test audit records
        audit_records = [
            {
                "id": "success-id",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "conflict-id",
                "changed_at": "2024-10-10 11:35:05.123456",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "CREATE",
                "ip_address": "192.168.1.2",
                "route_payload": {"key": "value2"},
            },
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify results
        assert result["success"] == 1
        assert result["failed"] == 0  # Conflicts are not counted as failures
        assert len(result["errors"]) == 0  # No general errors
        assert len(result["conflicts"]) == 1  # One conflict identified
        assert result["conflicts"][0]["id"] == "conflict-id"
        assert (
            "version conflict" in result["conflicts"][0]["error"]
        )  # Error reason captured
        mock_bulk.assert_called_once()

    @patch("app.elasticsearch.client.Path")
    @patch("app.elasticsearch.client.Elasticsearch")
    @patch("elasticsearch.helpers.bulk")
    def test_bulk_sync_audit_records_with_other_errors(
        self, mock_bulk, mock_elasticsearch, mock_path
    ):
        """Test bulk_sync_audit_records with other types of errors."""
        # Mock the Path.exists() to return True
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True

        # Mock the Elasticsearch client
        mock_es_instance = Mock()
        mock_elasticsearch.return_value = mock_es_instance
        mock_es_instance.info.return_value = {"version": {"number": "8.11.0"}}

        # Mock the bulk operation to return success count and failed
        # items with other errors
        mock_bulk.return_value = (
            1,  # 1 success
            [  # Failed items list with other error
                {
                    "create": {
                        "_index": "test-index",
                        "_id": "error-id",
                        "status": 400,
                        "error": {
                            "type": "illegal_argument_exception",
                            "reason": "Invalid field value",
                        },
                    }
                }
            ],
        )

        # Create the client
        client = ElasticsearchClient()

        # Test audit records
        audit_records = [
            {
                "id": "success-id",
                "changed_at": "2024-10-10 11:34:05.123456",
                "handler_id": "handler-123",
                "handled_ids": [1, 2, 3],
                "change_type": "CREATE",
                "ip_address": "192.168.1.1",
                "route_payload": {"key": "value"},
            },
            {
                "id": "error-id",
                "changed_at": "2024-10-10 11:35:05.123456",
                "handler_id": "handler-124",
                "handled_ids": [4, 5, 6],
                "change_type": "CREATE",
                "ip_address": "192.168.1.2",
                "route_payload": {"key": "value2"},
            },
        ]

        # Call bulk_sync_audit_records
        result = client.bulk_sync_audit_records(audit_records)

        # Verify results
        assert result["success"] == 1
        assert result["failed"] == 1  # Other errors are counted as failures
        assert len(result["errors"]) == 1  # One general error
        assert len(result["conflicts"]) == 0  # No conflicts
        assert result["errors"][0]["id"] == "error-id"
        assert "Invalid field value" in result["errors"][0]["error"]
        mock_bulk.assert_called_once()
