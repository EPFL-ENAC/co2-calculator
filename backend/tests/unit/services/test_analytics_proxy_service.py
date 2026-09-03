"""#2649 — the Matomo proxy must forward what Matomo needs and nothing else.

The proxy exists because content blockers drop ``matomo.js``/``matomo.php`` by
filename; these tests pin the parts that make the proxied hit equivalent to a
direct one (client IP, user agent, language) and the parts that must never
cross (our session cookie, an authenticated write).
"""

import httpx
import pytest

from app.core.config import get_settings
from app.services import analytics_proxy_service
from app.services.analytics_proxy_service import AnalyticsProxyService, TrackingHit

UPSTREAM = "https://matomo.test/piwik/"


@pytest.fixture(autouse=True)
def _reset_script_cache():
    analytics_proxy_service._cached_script = None
    analytics_proxy_service._cached_at = 0.0
    yield
    analytics_proxy_service._cached_script = None
    analytics_proxy_service._cached_at = 0.0


@pytest.fixture
def matomo_url(monkeypatch):
    monkeypatch.setattr(get_settings(), "MATOMO_URL", UPSTREAM)
    return UPSTREAM


def service_recording(requests: list[httpx.Request], response: httpx.Response):
    """A service whose upstream calls are captured instead of sent."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response

    return AnalyticsProxyService(
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def hit(**overrides) -> TrackingHit:
    fields = {
        "params": {"idsite": "1", "rec": "1", "url": "https://co2.test/en/_/2024"},
        "body": None,
        "content_type": None,
        "user_agent": "Mozilla/5.0",
        "accept_language": "fr-CH",
        "client_ip": "128.178.1.2",
    }
    fields.update(overrides)
    return TrackingHit(**fields)


@pytest.mark.asyncio
async def test_script_is_fetched_from_matomo_and_then_cached(matomo_url):
    requests: list[httpx.Request] = []
    service = service_recording(
        requests,
        httpx.Response(
            200,
            content=b"/* matomo */",
            headers={"content-type": "application/javascript"},
        ),
    )

    first = await service.fetch_script()
    second = await service.fetch_script()

    assert first.body == b"/* matomo */"
    assert first.content_type == "application/javascript"
    assert second == first
    # One upstream fetch for two calls: the tracker changes on upgrade only.
    assert len(requests) == 1
    assert str(requests[0].url) == "https://matomo.test/piwik/matomo.js"


@pytest.mark.asyncio
async def test_hit_carries_client_ip_and_agent_but_no_cookie(matomo_url):
    requests: list[httpx.Request] = []
    service = service_recording(requests, httpx.Response(204))

    await service.forward_hit(hit())

    sent = requests[0]
    assert sent.method == "GET"
    assert str(sent.url).startswith("https://matomo.test/piwik/matomo.php?")
    assert sent.url.params["idsite"] == "1"
    # Without the real client IP, cookieless tracking collapses every visitor
    # into the pod's egress address.
    assert sent.headers["x-forwarded-for"] == "128.178.1.2"
    assert sent.headers["user-agent"] == "Mozilla/5.0"
    assert sent.headers["accept-language"] == "fr-CH"
    assert "cookie" not in sent.headers
    assert "authorization" not in sent.headers


@pytest.mark.asyncio
async def test_post_hit_forwards_the_body(matomo_url):
    requests: list[httpx.Request] = []
    service = service_recording(requests, httpx.Response(204))

    await service.forward_hit(
        hit(body=b'{"requests":["?idsite=1"]}', content_type="application/json")
    )

    sent = requests[0]
    assert sent.method == "POST"
    assert sent.content == b'{"requests":["?idsite=1"]}'
    assert sent.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_token_auth_is_refused_rather_than_relayed(matomo_url):
    requests: list[httpx.Request] = []
    service = service_recording(requests, httpx.Response(204))

    with pytest.raises(ValueError, match="token_auth"):
        await service.forward_hit(hit(params={"idsite": "1", "token_auth": "stolen"}))

    assert requests == []


@pytest.mark.asyncio
async def test_unusable_upstream_fails_loudly(monkeypatch):
    requests: list[httpx.Request] = []
    service = service_recording(requests, httpx.Response(204))

    monkeypatch.setattr(get_settings(), "MATOMO_URL", "")
    with pytest.raises(ValueError, match="not configured"):
        await service.forward_hit(hit())

    monkeypatch.setattr(get_settings(), "MATOMO_URL", "http://matomo.test/piwik/")
    with pytest.raises(ValueError, match="https"):
        await service.forward_hit(hit())

    assert requests == []
