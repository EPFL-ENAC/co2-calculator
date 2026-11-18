"""SSRF guard for form-supplied connection server URLs."""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import get_settings


def _allowed_suffixes() -> list[str]:
    raw = get_settings().CONNECTOR_ALLOWED_HOST_SUFFIXES
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _is_internal(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _reject_internal_host(host: str) -> None:
    """Fail closed unless every address the host resolves to is public."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError) as exc:
        raise ValueError(f"server_url host {host!r} does not resolve") from exc
    if any(_is_internal(str(info[4][0])) for info in infos):
        raise ValueError(f"server_url host {host!r} resolves to an internal address")


def validate_external_url(url: str) -> str:
    """Return ``url`` if it is https and its host matches the allowlist.

    SSRF guard for a form-supplied ``server_url``. Fails closed when the
    allowlist is empty. Suffix match is on a dot boundary so ``evil-example.org``
    does not match ``example.org``. Resolves the host and rejects it when any
    address is internal, so an allowed name cannot point inside the network.
    """
    suffixes = _allowed_suffixes()
    if not suffixes:
        raise ValueError("CONNECTOR_ALLOWED_HOST_SUFFIXES is not configured")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("server_url must use https")
    host = (parsed.hostname or "").lower()
    if not any(host == s or host.endswith("." + s) for s in suffixes):
        raise ValueError(f"server_url host {host!r} is not in the allowlist")
    _reject_internal_host(host)
    return url
