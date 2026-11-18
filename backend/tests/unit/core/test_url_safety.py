import socket

import pytest

from app.core import url_safety
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _restore_settings_cache():
    """Clear the lru_cache after each test too, so once monkeypatch reverts
    the env, the next caller re-reads real settings instead of the blanked
    values left behind by a fail-closed test.
    """
    yield
    get_settings.cache_clear()


PUBLIC_IP = "128.178.1.1"


def _resolve_to(monkeypatch, ip):
    """Stub DNS so tests never touch the network."""

    def fake(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    _resolve_to(monkeypatch, PUBLIC_IP)


def _set(monkeypatch, suffixes):
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", suffixes)
    url_safety.get_settings.cache_clear()


def test_allows_https_matching_suffix(monkeypatch):
    _set(monkeypatch, "example.org")
    assert url_safety.validate_external_url("https://tableau.example.org/") == (
        "https://tableau.example.org/"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://tableau.example.org/",  # not https
        "https://tableau.evil.com/",  # host not allowed
        "https://evil-example.org/",  # suffix not on a dot boundary
        "https://169.254.169.254/",  # cloud metadata
    ],
)
def test_rejects_unsafe(monkeypatch, url):
    _set(monkeypatch, "example.org")
    with pytest.raises(ValueError):
        url_safety.validate_external_url(url)


def test_fails_closed_when_allowlist_empty(monkeypatch):
    _set(monkeypatch, "")
    with pytest.raises(ValueError):
        url_safety.validate_external_url("https://tableau.example.org/")


@pytest.mark.parametrize(
    "ip", ["10.0.0.1", "127.0.0.1", "169.254.169.254", "::1", "0.0.0.0"]
)
def test_rejects_allowed_host_resolving_to_internal_address(monkeypatch, ip):
    _set(monkeypatch, "example.org")
    _resolve_to(monkeypatch, ip)
    with pytest.raises(ValueError):
        url_safety.validate_external_url("https://tableau.example.org/")


def test_rejects_unresolvable_host(monkeypatch):
    _set(monkeypatch, "example.org")

    def fail(host, *args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(ValueError):
        url_safety.validate_external_url("https://tableau.example.org/")
