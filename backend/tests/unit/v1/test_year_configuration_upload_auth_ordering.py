"""Regression tests for #2261 on the reduction-objective upload route.

``POST /v1/year-configuration/{year}/upload`` had the identical hole to
``POST /v1/files/temp-upload``: declaring ``file: UploadFile = File(...)`` /
``category: FileCategory = Form(...)`` makes FastAPI read the *entire*
multipart body (``fastapi/routing.py``: ``body = await request.form()``)
before resolving any dependency, so an unauthenticated caller could push an
arbitrary payload through before the 401. This route was worse: it had no
size cap at all, where temp-upload at least carried ``check_size``.

The ``_find_route`` walker is shared with the temp-upload regression tests
rather than duplicated — both need to reach through FastAPI's nested
``_IncludedRouter`` wrappers.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import year_configuration as year_config_module
from app.main import app
from app.models.user import User
from tests.unit.v1.test_temp_upload_auth_ordering import _find_route

UPLOAD_PATH = "/api/v1/year-configuration/2025/upload"


@pytest.fixture
def authorised_editor(monkeypatch):
    """Authenticate as a user the permission check accepts.

    ``is_permitted`` reaches OPA, so it is patched on the endpoint module
    where the name is bound; the point of these tests is the *ordering* of
    auth against body parsing, not the permission decision itself.
    """
    fake = MagicMock(spec=User)
    fake.id = 1
    app.dependency_overrides[get_current_user] = lambda: fake

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(year_config_module, "is_permitted", _allow)
    yield fake
    app.dependency_overrides.clear()


def test_unauthenticated_upload_never_reads_body():
    """No auth cookie -> 401, and the ASGI ``receive`` callable is never
    invoked: not one byte of the payload is pulled off the wire before the
    request is rejected.
    """
    boundary = b"----regressiontestboundary"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="x.csv"\r\n'
        b"Content-Type: text/csv\r\n\r\n"
        b"col1,col2\n1,2\n\r\n"
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="category"\r\n\r\n'
        b"footprint\r\n"
        b"--" + boundary + b"--\r\n"
    )
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
        "path": UPLOAD_PATH,
        "raw_path": UPLOAD_PATH.encode(),
        "query_string": b"",
        "root_path": "",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "headers": [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(body)).encode()),
        ],
    }

    asyncio.run(app(scope, receive, send))

    assert receive_calls == 0, (
        "auth must reject the request before the body is ever read from the wire"
    )
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 401


def test_reduction_objective_upload_route_has_no_body_field():
    """Structural canary: reintroducing a ``File(...)``/``Form(...)`` param
    gives this route a non-None ``body_field`` and silently restores the
    pre-auth body parsing.
    """
    route = _find_route(app.routes, "/year-configuration/{year}/upload")
    assert route is not None, "reduction-objective upload route not found"
    assert route.body_field is None


def test_openapi_still_documents_the_multipart_body():
    """Parsing the body by hand means FastAPI generates no requestBody, so
    the schema is supplied via ``openapi_extra``. If that drifts, the
    generated frontend client loses the endpoint's shape silently.
    """
    schema = app.openapi()["paths"]["/v1/year-configuration/{year}/upload"]["post"]
    body = schema["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert body["required"] == ["file", "category"]
    assert body["properties"]["file"]["format"] == "binary"
    assert body["properties"]["category"]["enum"] == [
        "footprint",
        "population",
        "scenarios",
    ]


def test_oversized_file_is_rejected_after_auth(authorised_editor):
    """This route previously had no size limit at all. Authenticated abuse
    is now bounded by the same per-file cap temp-upload uses.
    """
    original_max_size = year_config_module.file_checker.max_size
    year_config_module.file_checker.max_size = 5  # bytes, for a cheap payload
    try:
        with TestClient(app) as client:
            resp = client.post(
                UPLOAD_PATH,
                files={"file": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
                data={"category": "footprint"},
            )
        assert resp.status_code == 400, resp.text
        assert "exceeds max size" in resp.text
    finally:
        year_config_module.file_checker.max_size = original_max_size


def test_upload_rejects_non_file_value_for_file_field(authorised_editor):
    """Manual parsing skips FastAPI's automatic UploadFile validation, so a
    plain string under the 'file' field must 422 rather than crash on
    ``.filename`` downstream.
    """
    with TestClient(app) as client:
        resp = client.post(
            UPLOAD_PATH,
            data={"file": "not-a-file", "category": "footprint"},
        )
    assert resp.status_code == 422, resp.text


def test_upload_rejects_unknown_category(authorised_editor):
    """``FileCategory`` is a ``Literal``; hand-parsing loses FastAPI's
    validation of it, so the endpoint must reject unknown values itself
    instead of failing later on the ``category_map`` lookup.
    """
    with TestClient(app) as client:
        resp = client.post(
            UPLOAD_PATH,
            files={"file": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
            data={"category": "bogus"},
        )
    assert resp.status_code == 422, resp.text
