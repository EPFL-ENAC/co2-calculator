"""Unit tests for exception handlers.

Tests cover:
- permission_denied_handler
- db_unavailable_handler
"""

import importlib
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.middleware.exceptions import ExceptionMiddleware

from app.core.exception_handlers import (
    db_unavailable_handler,
    permission_denied_handler,
)
from app.core.exceptions import (
    InsufficientScopeError,
    PermissionDeniedError,
    RecordAccessDeniedError,
)
from app.main import app as main_app

app_main = importlib.import_module("app.main")


def _stack_exception_handlers(app: FastAPI) -> dict:
    """The handlers ExceptionMiddleware actually holds in a built stack."""
    node = app.middleware_stack
    while not isinstance(node, ExceptionMiddleware):
        node = node.app
    return node._exception_handlers


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


def _client_raising(exc: Exception) -> TestClient:
    """A bare app wired like main.app, with one route that raises ``exc``."""
    app = FastAPI()
    app.add_exception_handler(SQLAlchemyTimeoutError, db_unavailable_handler)
    app.add_exception_handler(DBAPIError, db_unavailable_handler)

    @app.get("/boom")
    async def boom():
        raise exc

    return TestClient(app, raise_server_exceptions=False)


class TestDbUnavailableHandler:
    """A DB outage answers 503 JSON; every other error stays a 500."""

    def test_main_app_wires_the_handler(self):
        for exc_class in (SQLAlchemyTimeoutError, DBAPIError):
            assert main_app.exception_handlers[exc_class] is db_unavailable_handler

    def test_handlers_survive_opentelemetry_instrument(self):
        """#3218: prod answered 500, not 503, on a PgBouncer outage.

        Under opentelemetry-instrument, exclude_per_chunk_asgi_spans() builds
        the middleware stack mid-module, and Starlette copies the handlers
        into ExceptionMiddleware at that moment: handlers registered after
        it were in ``app.exception_handlers`` but never ran. Re-import
        app.main the way prod boots it and look inside the built stack.
        """
        saved = dict(vars(app_main))
        instrumentor = FastAPIInstrumentor()
        instrumentor.instrument()
        try:
            importlib.reload(app_main)
            handlers = _stack_exception_handlers(app_main.app)
        finally:
            instrumentor.uninstrument()
            vars(app_main).update(saved)

        for exc_class in (SQLAlchemyTimeoutError, DBAPIError):
            assert handlers.get(exc_class) is db_unavailable_handler
        assert handlers.get(PermissionDeniedError) is not None

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(
                SQLAlchemyTimeoutError("QueuePool limit of size 5 overflow 10 reached"),
                id="pool-checkout-timeout",
            ),
            pytest.param(
                OperationalError(
                    "SELECT 1",
                    {},
                    psycopg.OperationalError("server closed the connection"),
                    connection_invalidated=True,
                ),
                id="connection-lost-or-never-established",
            ),
            pytest.param(
                InterfaceError(
                    "SELECT 1",
                    {},
                    psycopg.InterfaceError("the connection is lost"),
                    connection_invalidated=True,
                ),
                id="connection-lost-as-interface-error",
            ),
            pytest.param(
                OperationalError(
                    "SELECT 1",
                    {},
                    psycopg.errors.ProtocolViolation("query_wait_timeout"),
                ),
                id="pgbouncer-query-wait-timeout",
            ),
            pytest.param(
                OperationalError(
                    None,
                    None,
                    psycopg.OperationalError(
                        "connection failed: FATAL:  sorry, too many clients already"
                    ),
                ),
                id="too-many-connections-53300",
            ),
            pytest.param(
                OperationalError(
                    None,
                    None,
                    psycopg.OperationalError(
                        'connection failed: connection to server at "10.0.0.1", '
                        "port 5432 failed: FATAL:  server login has been failing, "
                        "cached error: connect failed (server_login_retry)"
                    ),
                ),
                id="pgbouncer-server-login-retry-3218",
            ),
        ],
    )
    def test_db_unavailable_is_503(self, exc):
        with patch("app.core.exception_handlers.logger") as log:
            resp = _client_raising(exc).get("/boom")

        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert resp.json() == {"detail": "database_unavailable"}
        assert resp.headers["Retry-After"] == "30"
        # Answering 503 must not swallow the error: one line, no traceback.
        log.error.assert_called_once()
        assert "exc_info" not in log.error.call_args.kwargs
        assert log.error.call_args.kwargs["extra"]["event"] == "db_unavailable"
        assert log.error.call_args.kwargs["extra"]["path"] == "/boom"

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(
                OperationalError(
                    "SELECT 1",
                    {},
                    psycopg.errors.QueryCanceled("canceling statement due to timeout"),
                ),
                id="other-operational-error",
            ),
            pytest.param(
                IntegrityError(
                    "INSERT", {}, psycopg.errors.UniqueViolation("duplicate key")
                ),
                id="integrity-error",
            ),
            pytest.param(RuntimeError("boom"), id="plain-bug"),
        ],
    )
    def test_other_errors_stay_500(self, exc):
        resp = _client_raising(exc).get("/boom")

        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
