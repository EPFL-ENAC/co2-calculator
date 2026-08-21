"""Regression tests for #2261: auth must run before the upload body is read.

``POST /v1/files/temp-upload`` used to declare ``files: list[UploadFile] =
File(...)`` directly on the endpoint. FastAPI reads the *entire* multipart
body (``fastapi/routing.py``: ``body = await request.form()``) before
resolving any dependency the moment a route has a File/Form body param —
regardless of dependency order — so an unauthenticated caller could push an
arbitrary payload through before the 401 was raised. The fix takes the raw
``Request`` and only calls ``request.form()`` after the permission check.

These tests intentionally do *not* use ``test_files_security.py``'s
autouse fixture, which overrides ``get_current_user`` — that would make
the auth path a no-op and the test would prove nothing.
"""

import asyncio
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import files as files_module
from app.main import app
from app.models.user import User


def _build_multipart_body() -> tuple[bytes, bytes]:
    boundary = b"----regressiontestboundary"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="files"; filename="x.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n"
        b"col1,col2\n1,2\n\r\n"
        b"--" + boundary + b"--\r\n"
    )
    return body, boundary


def _override_authenticated_editor() -> None:
    fake = MagicMock(spec=User)
    fake.id = 1
    fake.calculate_permissions.return_value = {
        "backoffice.configuration": ["edit"],
    }
    app.dependency_overrides[get_current_user] = lambda: fake


def test_unauthenticated_upload_never_reads_body():
    """No auth cookie -> 401, and the ASGI ``receive`` callable (the body
    stream) is never invoked -- the server never pulled a single byte of
    the payload off the wire before rejecting the request.
    """
    body, boundary = _build_multipart_body()
    receive_calls = 0

    async def receive():
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": body, "more_body": False}

    messages: list[dict] = []

    async def send(message: dict) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/files/temp-upload",
        "raw_path": b"/api/v1/files/temp-upload",
        "query_string": b"",
        "root_path": "",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "headers": [
            (
                b"content-type",
                b"multipart/form-data; boundary=" + boundary,
            ),
            (b"content-length", str(len(body)).encode()),
        ],
    }

    asyncio.run(app(scope, receive, send))

    assert receive_calls == 0, (
        "auth must reject the request before the body is ever read from the wire"
    )
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 401


def _find_route(routes, target_suffix: str, prefix: str = ""):
    """Recurse through FastAPI's nested ``_IncludedRouter`` wrappers (one
    per ``include_router`` call) to find the ``APIRoute`` whose combined
    path ends with ``target_suffix``.
    """
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            sub_prefix = prefix + route.include_context.prefix
            found = _find_route(route.original_router.routes, target_suffix, sub_prefix)
            if found is not None:
                return found
        else:
            full_path = prefix + getattr(route, "path", "")
            if full_path.endswith(target_suffix):
                return route
    return None


def test_temp_upload_route_has_no_body_field():
    """Structural canary: if someone reintroduces a ``File(...)``/``Form(...)``
    param (directly or via a route ``dependencies=[...]`` entry), FastAPI
    will compute a non-None ``body_field`` for this route and silently
    restore the pre-auth body parsing this test guards against.
    """
    route = _find_route(app.routes, "/files/temp-upload")
    assert route is not None, "temp-upload route not found"
    assert route.body_field is None


def test_oversized_file_is_rejected_after_auth():
    """An authenticated caller still gets the size limit enforced (via
    ``file_checker.check_size``, now called manually after the body is
    parsed) -- dropping the automatic dependency must not silently drop
    the check.
    """
    original_max_size = files_module.file_checker.max_size
    files_module.file_checker.max_size = 5  # bytes, for a cheap test payload
    _override_authenticated_editor()

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/files/temp-upload",
                files={"files": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
            )
        assert resp.status_code == 400, resp.text
        assert "exceeds max size" in resp.text
    finally:
        files_module.file_checker.max_size = original_max_size
        app.dependency_overrides.clear()


def test_upload_rejects_non_file_form_value_for_files_field():
    """Manual parsing skips FastAPI's automatic UploadFile validation, so a
    plain string sent under the 'files' field must be rejected with 422
    instead of crashing on ``.filename`` downstream.
    """
    _override_authenticated_editor()

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/files/temp-upload",
                data={"files": "not-a-file"},
            )
        assert resp.status_code == 422, resp.text
    finally:
        app.dependency_overrides.clear()
