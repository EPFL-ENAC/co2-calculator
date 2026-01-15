"""Unit tests for exception handlers.

Tests cover:
- permission_denied_handler
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exception_handlers import permission_denied_handler
from app.core.exceptions import (
    InsufficientScopeError,
    PermissionDeniedError,
    RecordAccessDeniedError,
)


class TestPermissionDeniedHandler:
    """Tests for permission_denied_handler."""

    @pytest.mark.asyncio
    async def test_permission_denied_handler_basic(self):
        """Test permission_denied_handler with basic PermissionDeniedError."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/modules/12345/2024/headcount"
        request.method = "GET"

        error = PermissionDeniedError(
            required_permission="modules.headcount",
            action="view",
            message="User does not have view permission",
        )

        # Mock logger to avoid "message" key conflict
        with patch("app.core.exception_handlers.logger") as _:
            response = await permission_denied_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        content = response.body.decode()
        assert "Permission denied" in content
        assert "modules.headcount" in content

    @pytest.mark.asyncio
    async def test_permission_denied_handler_insufficient_scope(self):
        """Test permission_denied_handler with InsufficientScopeError."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/modules/12345/2024/equipment"
        request.method = "GET"

        error = InsufficientScopeError(
            required_permission="modules.equipment",
            action="edit",
            message="User scope insufficient",
            user_scope="unit:12345",
            required_scope="unit:99999",
        )

        # Mock logger to avoid "message" key conflict
        with patch("app.core.exception_handlers.logger") as _:
            response = await permission_denied_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        content = response.body.decode()
        assert "Permission denied" in content
        assert "scope" in content

    @pytest.mark.asyncio
    async def test_permission_denied_handler_record_access_denied(self):
        """Test permission_denied_handler with RecordAccessDeniedError."""
        request = MagicMock(spec=Request)
        request.url.path = (
            "/api/v1/modules/12345/2024/professional-travel/equipment/123"
        )
        request.method = "PATCH"

        error = RecordAccessDeniedError(
            required_permission="modules.professional_travel",
            action="edit",
            message="Record is read-only",
            record_id=123,
            reason="API-synced trip",
        )

        # Mock logger to avoid "message" key conflict
        with patch("app.core.exception_handlers.logger") as _:
            response = await permission_denied_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        content = response.body.decode()
        assert "Permission denied" in content
        assert "record" in content

    @pytest.mark.asyncio
    async def test_permission_denied_handler_unexpected_exception(self):
        """Test permission_denied_handler with unexpected exception type."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"

        # Pass a regular Exception instead of PermissionDeniedError
        error = Exception("Unexpected error")

        response = await permission_denied_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        content = response.body.decode()
        assert "Permission denied" in content

    @pytest.mark.asyncio
    async def test_permission_denied_handler_record_without_id(self):
        """Test permission_denied_handler with RecordAccessDeniedError without record_id."""  # noqa: E501
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/modules/12345/2024/equipment"
        request.method = "POST"

        error = RecordAccessDeniedError(
            required_permission="modules.equipment",
            action="create",
            message="Cannot create record",
            record_id=None,
            reason="Insufficient permissions",
        )

        # Mock logger to avoid "message" key conflict
        with patch("app.core.exception_handlers.logger") as _:
            response = await permission_denied_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_permission_denied_handler_insufficient_scope_optional_fields(self):
        """Test permission_denied_handler with InsufficientScopeError without optional fields."""  # noqa: E501
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/modules/12345/2024/headcount"
        request.method = "GET"

        error = InsufficientScopeError(
            required_permission="modules.headcount",
            action="view",
            message="Scope mismatch",
        )

        # Mock logger to avoid "message" key conflict
        with patch("app.core.exception_handlers.logger") as _:
            response = await permission_denied_handler(request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_403_FORBIDDEN
