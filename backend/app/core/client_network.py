"""Refuse clients outside the allowed networks (#3196).

The host sits on the public load balancer, so the frontend can show an info
page to clients off the institution network. The API must stay closed to
them. The OpenShift router only sees the load balancer, so the check reads
the client address that uvicorn resolved from X-Forwarded-For with
FORWARDED_ALLOW_IPS: the right-most address that is not a trusted proxy.

Raw ASGI, like RequestOriginMiddleware, so streaming responses pass through.
"""

from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Exact paths: /health/deps and the other /health routes stay closed.
PROBE_PATHS = frozenset({"/healthz", "/ready"})
# Pod-to-pod routes (app.api.internal). They keep their own token and
# live-pod checks.
INTERNAL_PREFIX = "/internal/"


def is_direct_call(scope: Scope) -> bool:
    """True for a probe or an internal path called without X-Forwarded-For.

    The kubelet and the other pods call the pod directly. The router and the
    load balancer always add the header, so these paths stay closed to their
    clients. A pod address is inside the trusted proxies, so is_allowed
    alone refuses it.
    """
    path = scope["path"]
    direct_path = path in PROBE_PATHS or path.startswith(INTERNAL_PREFIX)
    forwarded = any(name == b"x-forwarded-for" for name, _ in scope["headers"])
    return direct_path and not forwarded


def parse_networks(value: str) -> list[IPv4Network | IPv6Network]:
    """Split a comma-separated CIDR list. A wrong entry raises."""
    return [ip_network(part.strip()) for part in value.split(",") if part.strip()]


def is_allowed(
    host: str | None,
    networks: list[IPv4Network | IPv6Network],
    proxies: list[IPv4Network | IPv6Network],
) -> bool:
    """True if the host is an IP address inside the networks, not a proxy.

    A proxy address as the client means the chain had no client address in
    front of it: fail closed, even if a wide network such as 10.0.0.0/8
    holds the proxies.
    """
    if host is None:
        return False
    try:
        address = ip_address(host)
    except ValueError:
        return False
    if any(address in proxy for proxy in proxies):
        return False
    return any(address in network for network in networks)


class ClientNetworkMiddleware:
    """403 for a client outside the networks. No network turns the check off."""

    def __init__(self, app: ASGIApp, allowed_cidrs: str, trusted_proxies: str) -> None:
        self.app = app
        self.networks = parse_networks(allowed_cidrs)
        self.proxies = parse_networks(trusted_proxies)
        if self.networks and not self.proxies:
            # uvicorn would then see the router pod as every client.
            raise ValueError("CLIENT_ALLOWED_CIDRS needs FORWARDED_ALLOW_IPS")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        client = scope.get("client")
        host = client[0] if client else None
        refused = (
            scope["type"] == "http"
            and bool(self.networks)
            and not is_direct_call(scope)
            and not is_allowed(host, self.networks, self.proxies)
        )
        if not refused:
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            status_code=403,
            content={"detail": "Client network not allowed"},
        )
        await response(scope, receive, send)
