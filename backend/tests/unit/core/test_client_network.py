"""The API refuses clients outside the allowed networks (#3196)."""

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.client_network import ClientNetworkMiddleware

# Documentation ranges (RFC 5737, RFC 3849): the real list is a Helm value.
ALLOWED = "198.51.100.0/24, 10.0.0.0/8, 2001:db8:1::/48"


PROXIES = "10.20.0.0/16, 10.98.42.0/24"


def _client(host: str, cidrs: str = ALLOWED, proxies: str = PROXIES) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        ClientNetworkMiddleware, allowed_cidrs=cidrs, trusted_proxies=proxies
    )

    @app.get("/v1/units")
    def units() -> dict:
        return {"ok": True}

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.post("/internal/cache/taxonomy/clear")
    def clear() -> dict:
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.close()

    @app.get("/health/deps")
    def deps() -> dict:
        return {"ok": True}

    return TestClient(app, client=(host, 50000))


@pytest.mark.parametrize("host", ["198.51.100.7", "10.5.1.1", "2001:db8:1::1"])
def test_inside_client_reaches_the_api(host: str) -> None:
    assert _client(host).get("/v1/units").status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "203.0.113.5",
        "2001:db8:2::1",
        "testclient",
        # A proxy as the client: no client address in front of it. Inside
        # 10.0.0.0/8, still refused.
        "10.20.1.1",
        "10.98.42.215",
    ],
)
def test_outside_client_gets_403(host: str) -> None:
    response = _client(host).get("/v1/units")
    assert response.status_code == 403
    assert response.json() == {"detail": "Client network not allowed"}


def test_direct_probe_answers_any_address() -> None:
    # The kubelet: no X-Forwarded-For header.
    assert _client("203.0.113.5").get("/healthz").status_code == 200


@pytest.mark.parametrize("forwarded", ["203.0.113.5", "198.51.100.7", ""])
def test_probe_through_a_proxy_stays_closed(forwarded: str) -> None:
    # The header is there, so the request came through the router. Its
    # value does not matter: uvicorn already resolved the client from it.
    response = _client("203.0.113.5").get(
        "/healthz", headers={"X-Forwarded-For": forwarded}
    )
    assert response.status_code == 403


def test_pod_reaches_the_internal_routes() -> None:
    # A pod address is inside the trusted proxies: no header, direct call.
    response = _client("10.20.1.1").post("/internal/cache/taxonomy/clear")
    assert response.status_code == 200


def test_internal_route_through_a_proxy_stays_closed() -> None:
    response = _client("203.0.113.5").post(
        "/internal/cache/taxonomy/clear",
        headers={"X-Forwarded-For": "203.0.113.5"},
    )
    assert response.status_code == 403


def test_other_health_routes_stay_closed() -> None:
    assert _client("203.0.113.5").get("/health/deps").status_code == 403


def test_list_without_proxies_fails_at_startup() -> None:
    with pytest.raises(ValueError, match="FORWARDED_ALLOW_IPS"):
        _client("198.51.100.7", proxies="").get("/v1/units")


def test_empty_list_turns_the_check_off() -> None:
    assert _client("203.0.113.5", cidrs="").get("/v1/units").status_code == 200


@pytest.mark.parametrize("proxies", ["10.20.0.1/16", "router.local", "unix:/tmp/x"])
def test_check_off_leaves_the_proxy_list_to_uvicorn(proxies: str) -> None:
    # uvicorn accepts these FORWARDED_ALLOW_IPS shapes: with the check off,
    # the app must start as before.
    client = _client("203.0.113.5", cidrs="", proxies=proxies)
    assert client.get("/v1/units").status_code == 200


def test_outside_client_cannot_open_a_websocket() -> None:
    with pytest.raises(WebSocketDisconnect):
        with _client("203.0.113.5").websocket_connect("/ws"):
            pass


def test_inside_client_opens_a_websocket() -> None:
    with _client("198.51.100.7").websocket_connect("/ws"):
        pass


def test_inside_client_through_a_proxy_reaches_the_probe() -> None:
    # The rule only keeps outside clients away: an allowed client that
    # comes through the router reaches the probe as before this change.
    response = _client("198.51.100.7").get(
        "/healthz", headers={"X-Forwarded-For": "198.51.100.7"}
    )
    assert response.status_code == 200


def test_wrong_cidr_fails_at_startup() -> None:
    with pytest.raises(ValueError):
        _client("198.51.100.7", cidrs="198.51.100.0/33").get("/v1/units")
