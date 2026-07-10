"""SSRF guard for form-supplied connection server URLs."""

from urllib.parse import urlparse

from app.core.config import get_settings


def _allowed_suffixes() -> list[str]:
    raw = get_settings().CONNECTOR_ALLOWED_HOST_SUFFIXES
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def validate_external_url(url: str) -> str:
    """Return ``url`` if it is https and its host matches the allowlist.

    SSRF guard for a form-supplied ``server_url``. Fails closed when the
    allowlist is empty. Suffix match is on a dot boundary so ``evil-epfl.ch``
    does not match ``epfl.ch``.
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
    return url
