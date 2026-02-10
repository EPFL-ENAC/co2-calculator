"""Unit tests for custom exceptions.

Tests cover:
- PermissionDeniedError
- InsufficientScopeError
- RecordAccessDeniedError
"""

from app.core.exceptions import (
    InsufficientScopeError,
    PermissionDeniedError,
    RecordAccessDeniedError,
)


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_permission_denied_error_creation(self):
        """Test creating PermissionDeniedError."""
        error = PermissionDeniedError(
            required_permission="modules.headcount",
            action="edit",
            message="User does not have edit permission",
        )
        assert error.required_permission == "modules.headcount"
        assert error.action == "edit"
        assert error.message == "User does not have edit permission"
        assert str(error) == "User does not have edit permission"

    def test_permission_denied_error_inheritance(self):
        """Test PermissionDeniedError is an Exception."""
        error = PermissionDeniedError(
            required_permission="modules.equipment",
            action="view",
            message="Access denied",
        )
        assert isinstance(error, Exception)


class TestInsufficientScopeError:
    """Tests for InsufficientScopeError."""

    def test_insufficient_scope_error_creation(self):
        """Test creating InsufficientScopeError."""
        error = InsufficientScopeError(
            required_permission="modules.headcount",
            action="edit",
            message="User scope insufficient",
            user_scope="unit:12345",
            required_scope="unit:99999",
        )
        assert error.required_permission == "modules.headcount"
        assert error.action == "edit"
        assert error.message == "User scope insufficient"
        assert error.user_scope == "unit:12345"
        assert error.required_scope == "unit:99999"
        assert isinstance(error, PermissionDeniedError)

    def test_insufficient_scope_error_optional_fields(self):
        """Test InsufficientScopeError with optional fields."""
        error = InsufficientScopeError(
            required_permission="modules.equipment",
            action="view",
            message="Scope mismatch",
        )
        assert error.user_scope is None
        assert error.required_scope is None


class TestRecordAccessDeniedError:
    """Tests for RecordAccessDeniedError."""

    def test_record_access_denied_error_creation(self):
        """Test creating RecordAccessDeniedError."""
        error = RecordAccessDeniedError(
            required_permission="modules.professional_travel",
            action="edit",
            message="Record is read-only",
            record_id=123,
            reason="API-synced trip",
        )
        assert error.required_permission == "modules.professional_travel"
        assert error.action == "edit"
        assert error.message == "Record is read-only"
        assert error.record_id == 123
        assert error.reason == "API-synced trip"
        assert isinstance(error, PermissionDeniedError)

    def test_record_access_denied_error_optional_fields(self):
        """Test RecordAccessDeniedError with optional fields."""
        error = RecordAccessDeniedError(
            required_permission="modules.headcount",
            action="delete",
            message="Cannot delete record",
        )
        assert error.record_id is None
        assert error.reason is None

    def test_record_access_denied_error_string_record_id(self):
        """Test RecordAccessDeniedError with string record_id."""
        error = RecordAccessDeniedError(
            required_permission="modules.equipment",
            action="edit",
            message="Access denied",
            record_id="equipment-123",
        )
        assert error.record_id == "equipment-123"
