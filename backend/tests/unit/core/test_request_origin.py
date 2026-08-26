"""Regression tests for #89: cookie-authenticated writes must prove their origin.

`SameSite=Lax` treats every `*.epfl.ch` sibling as same-site, so it cannot tell
our frontend from a compromised neighbour. `RequestOriginMiddleware` is what
does. Each case below passes only because the middleware is in the stack.

The middleware is exercised through a minimal Starlette app rather than the
real FastAPI app: the rules are about headers and cookies alone, and the tiny
app keeps a failure pointing at the decision table instead of at routing,
auth, or the DB.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.config import Settings
from app.core.request_origin import RequestOriginMiddleware, build_allowed_origins

ALLOWED = frozenset({"https://co2-calculator.epfl.ch", "https://second.epfl.ch"})
AUTH_COOKIES = {"auth_token": "irrelevant-the-middleware-never-decodes-it"}


async def _ok(request):
    return PlainTextResponse("reached")


@pytest.fixture
def client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/write", _ok, methods=["POST"]),
            Route("/read", _ok, methods=["GET"]),
        ]
    )
    app.add_middleware(RequestOriginMiddleware, allowed_origins=ALLOWED)
    return TestClient(app, cookies=AUTH_COOKIES)


def test_safe_method_passes_despite_hostile_origin(client: TestClient) -> None:
    """GET is exempt — audited (#89): no state-changing GET exists in the app."""
    response = client.get("/read", headers={"Origin": "https://evil.com"})
    assert response.status_code == 200


def test_same_origin_fetch_site_passes(client: TestClient) -> None:
    response = client.post("/write", headers={"Sec-Fetch-Site": "same-origin"})
    assert response.status_code == 200


def test_none_fetch_site_passes(client: TestClient) -> None:
    """`none` is a user-initiated navigation, not a cross-document request."""
    response = client.post("/write", headers={"Sec-Fetch-Site": "none"})
    assert response.status_code == 200


def test_same_site_fetch_site_is_rejected(client: TestClient) -> None:
    """THE assertion of this file.

    A sibling under the shared registrable domain is `same-site`, which
    `SameSite=Lax` permits and this middleware exists to refuse. Rejecting
    only `cross-site` would leave the actual attack untouched.
    """
    response = client.post("/write", headers={"Sec-Fetch-Site": "same-site"})
    assert response.status_code == 403


def test_cross_site_fetch_site_is_rejected(client: TestClient) -> None:
    response = client.post("/write", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


def test_matching_origin_passes(client: TestClient) -> None:
    response = client.post(
        "/write", headers={"Origin": "https://co2-calculator.epfl.ch"}
    )
    assert response.status_code == 200


def test_foreign_origin_is_rejected(client: TestClient) -> None:
    response = client.post("/write", headers={"Origin": "https://evil.com"})
    assert response.status_code == 403


def test_origin_suffix_lookalike_is_rejected(client: TestClient) -> None:
    """Guards the comparison against ever becoming a substring/startswith test."""
    response = client.post(
        "/write", headers={"Origin": "https://co2-calculator.epfl.ch.evil.com"}
    )
    assert response.status_code == 403


def test_opaque_null_origin_is_rejected(client: TestClient) -> None:
    """A sandboxed iframe or a cross-origin redirect sends the literal `null`."""
    response = client.post("/write", headers={"Origin": "null"})
    assert response.status_code == 403


def test_additional_origin_passes(client: TestClient) -> None:
    response = client.post("/write", headers={"Origin": "https://second.epfl.ch"})
    assert response.status_code == 200


def test_referer_is_used_when_origin_absent(client: TestClient) -> None:
    response = client.post(
        "/write", headers={"Referer": "https://co2-calculator.epfl.ch/units/3"}
    )
    assert response.status_code == 200


def test_foreign_referer_is_rejected(client: TestClient) -> None:
    response = client.post("/write", headers={"Referer": "https://evil.com/page"})
    assert response.status_code == 403


def test_no_origin_headers_fails_closed(client: TestClient) -> None:
    """An unverifiable origin is a rejected origin — never a trusted one."""
    response = client.post("/write")
    assert response.status_code == 403


def test_request_without_auth_cookie_is_not_checked() -> None:
    """No cookie, no ambient authority to borrow — so nothing to forge.

    Such a request is not a CSRF vector; it falls through to normal
    authentication and is refused there instead.
    """
    app = Starlette(routes=[Route("/write", _ok, methods=["POST"])])
    app.add_middleware(RequestOriginMiddleware, allowed_origins=ALLOWED)
    response = TestClient(app).post(
        "/write", headers={"Authorization": "Bearer something"}
    )
    assert response.status_code == 200


def test_bearer_alongside_auth_cookie_is_still_checked(client: TestClient) -> None:
    """Cookies win: the cookie is the part a browser attaches for the attacker."""
    response = client.post("/write", headers={"Authorization": "Bearer something"})
    assert response.status_code == 403


def test_rejection_logs_a_single_capped_line(client: TestClient, caplog) -> None:
    """The origin reaches the log attacker-controlled — bound and flatten it."""
    hostile = "https://evil.com/" + "A" * 500 + "\nfake-log-line: injected"
    with caplog.at_level("WARNING"):
        response = client.post("/write", headers={"Origin": hostile})

    assert response.status_code == 403
    record = next(r for r in caplog.records if getattr(r, "csrf_blocked", False))
    assert "\n" not in record.reason
    assert len(record.reason) < 300


def test_allowlist_is_built_from_frontend_url() -> None:
    settings = Settings(
        FRONTEND_URL="https://co2-calculator.epfl.ch",
        CSRF_ADDITIONAL_ORIGINS=" https://second.epfl.ch , ",
    )
    assert build_allowed_origins(settings) == ALLOWED


def test_allowlist_normalizes_default_ports_and_drops_junk() -> None:
    """`https://host:443` and `https://host` are the same origin to a browser."""
    settings = Settings(
        FRONTEND_URL="https://co2-calculator.epfl.ch:443/app/",
        CSRF_ADDITIONAL_ORIGINS="not-a-url,http://localhost:9000",
    )
    assert build_allowed_origins(settings) == {
        "https://co2-calculator.epfl.ch",
        "http://localhost:9000",
    }
