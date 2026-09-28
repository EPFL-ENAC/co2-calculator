"""The renewed session cookie survives routes that build their own response (#2943).

FastAPI only merges a dependency's response headers into plain-data
returns. A 304, a download or an SSE stream would otherwise drop the
cookie while the renewal audit row claims it was renewed.
"""

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from fastapi.testclient import TestClient

from app.core.session_renewal import (
    RENEWED_COOKIE_STATE_KEY,
    SessionRenewalMiddleware,
)

COOKIE = "auth_token=renewed; HttpOnly; Path=/; SameSite=lax"


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionRenewalMiddleware)

    def renew(request: Request) -> None:
        setattr(request.state, RENEWED_COOKIE_STATE_KEY, COOKIE)

    @app.get("/json")
    def json_route(request: Request) -> dict:
        renew(request)
        return {"ok": True}

    @app.get("/not-modified")
    def not_modified(request: Request) -> Response:
        renew(request)
        return Response(status_code=304)

    @app.get("/stream")
    def stream(request: Request) -> StreamingResponse:
        renew(request)
        return StreamingResponse(iter([b"a", b"b"]))

    @app.get("/untouched")
    def untouched() -> PlainTextResponse:
        return PlainTextResponse("x")

    return app


def test_cookie_reaches_json_304_and_streaming_responses():
    client = TestClient(_app())
    for path in ("/json", "/not-modified", "/stream"):
        response = client.get(path)
        assert response.headers.get_list("set-cookie") == [COOKIE], path


def test_no_cookie_when_nothing_was_renewed():
    response = TestClient(_app()).get("/untouched")
    assert response.headers.get_list("set-cookie") == []
