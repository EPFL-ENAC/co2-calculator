"""Regression tests for #2261: auth must run before the upload body is read.

For any route declaring a File/Form parameter, FastAPI reads the *entire*
multipart body (``fastapi/routing.py``: ``body = await request.form()``)
before resolving any dependency — dependency order in the signature makes no
difference. That let an unauthenticated caller push an arbitrary payload
through before the 401.

The fix is ``AuthFirstRoute``, applied to the whole router: a route's handler
runs before that parsing, so the checks that don't need the body happen there
and the endpoints keep ordinary ``File(...)`` signatures.

These tests deliberately do *not* rely on ``dependency_overrides`` alone for
the authenticated cases — a route class sits outside dependency injection, so
overriding ``get_current_user`` does not satisfy it. They mint a real signed
token, which is also what makes them a genuine test of the gate.
"""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.auth_first_route import MAX_REQUEST_BODY_BYTES
from app.api.deps import get_current_user
from app.api.v1 import files as files_module
from app.core.security import create_access_token
from app.main import app
from app.models.user import User, UserProvider

TEMP_UPLOAD_PATH = "/api/v1/files/temp-upload"


def valid_access_token() -> str:
    """A real, correctly-signed, unexpired token.

    ``AuthFirstRoute`` verifies the signature and expiry itself, so the
    authenticated tests need a genuine token rather than a dependency
    override.
    """
    return create_access_token(
        data={
            "sub": "abc",
            "type": "access",
            "email": "uploader@example.org",
            "institutional_id": "123456",
            "provider": str(UserProvider.TEST.value),
        },
        expires_delta=timedelta(minutes=10),
    )


def authenticated_client() -> TestClient:
    fake = MagicMock(spec=User)
    fake.id = 1
    fake.calculate_permissions.return_value = {"backoffice.configuration": ["edit"]}
    app.dependency_overrides[get_current_user] = lambda: fake
    return TestClient(app, cookies={"auth_token": valid_access_token()})


def build_multipart_body(field: str = "files") -> tuple[bytes, bytes]:
    boundary = b"----regressiontestboundary"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="' + field.encode() + b'"; '
        b'filename="x.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n"
        b"col1,col2\n1,2\n\r\n"
        b"--" + boundary + b"--\r\n"
    )
    return body, boundary


def call_asgi(path: str, body: bytes, boundary: bytes, *, headers=None):
    """Drive the ASGI app directly, counting body reads.

    ``receive`` is the only way the server can pull the payload off the wire,
    so counting its calls is what proves the body was never read.
    """
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
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "headers": headers
        or [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    return receive_calls, start["status"]


def test_unauthenticated_upload_never_reads_body():
    """No auth cookie -> 401, and ``receive`` is never invoked: not one byte
    of the payload is pulled off the wire before the rejection.
    """
    body, boundary = build_multipart_body()
    receive_calls, status_code = call_asgi(TEMP_UPLOAD_PATH, body, boundary)

    assert receive_calls == 0, (
        "auth must reject the request before the body is ever read from the wire"
    )
    assert status_code == 401


def test_oversized_content_length_rejected_before_body_is_read():
    """A declared body over the ceiling is refused on the header alone, with
    a valid token — so the transfer is bounded even for a real user.
    """
    body, boundary = build_multipart_body()
    headers = [
        (b"content-type", b"multipart/form-data; boundary=" + boundary),
        (b"content-length", str(MAX_REQUEST_BODY_BYTES + 1).encode()),
        (b"cookie", b"auth_token=" + valid_access_token().encode()),
    ]
    receive_calls, status_code = call_asgi(
        TEMP_UPLOAD_PATH, body, boundary, headers=headers
    )

    assert receive_calls == 0, "oversized bodies must be refused on the header alone"
    assert status_code == 413


def test_upload_routes_use_auth_first_route():
    """Structural canary: dropping ``route_class`` restores the pre-auth body
    parsing this whole file exists to prevent, and every other test here
    would still pass on the happy path.
    """
    from app.api.auth_first_route import AuthFirstRoute

    route = find_route(app.routes, "/files/temp-upload")
    assert route is not None, "temp-upload route not found"
    assert isinstance(route, AuthFirstRoute)


def find_route(routes, target_suffix: str, prefix: str = ""):
    """Recurse through FastAPI's nested ``_IncludedRouter`` wrappers (one per
    ``include_router`` call) to find the route whose combined path ends with
    ``target_suffix``.
    """
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            sub_prefix = prefix + route.include_context.prefix
            found = find_route(route.original_router.routes, target_suffix, sub_prefix)
            if found is not None:
                return found
        else:
            full_path = prefix + getattr(route, "path", "")
            if full_path.endswith(target_suffix):
                return route
    return None


def test_oversized_file_is_rejected_after_auth():
    """The exact per-file cap still applies once the body is parsed — the
    coarse Content-Length ceiling is a pre-filter, not the enforcement point.
    """
    original_max_size = files_module.file_checker.max_size
    files_module.file_checker.max_size = 5  # bytes, for a cheap test payload
    try:
        with authenticated_client() as client:
            resp = client.post(
                TEMP_UPLOAD_PATH,
                files={"files": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
            )
        assert resp.status_code == 400, resp.text
        assert "exceeds max size" in resp.text
    finally:
        files_module.file_checker.max_size = original_max_size
        app.dependency_overrides.clear()


def test_upload_rejects_non_file_form_value_for_files_field():
    """A plain string under the 'files' field is rejected by FastAPI's own
    validation, which the endpoint gets back by keeping a File(...) signature.
    """
    try:
        with authenticated_client() as client:
            resp = client.post(TEMP_UPLOAD_PATH, data={"files": "not-a-file"})
        assert resp.status_code == 422, resp.text
    finally:
        app.dependency_overrides.clear()
