import pytest

from app.core import url_safety
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _restore_settings_cache():
    """Clear the lru_cache after each test too, so once monkeypatch reverts
    the env, the next caller re-reads real settings instead of the blanked
    values left behind by a fail-closed test."""
    yield
    get_settings.cache_clear()


def _set(monkeypatch, suffixes):
    monkeypatch.setenv("CONNECTOR_ALLOWED_HOST_SUFFIXES", suffixes)
    url_safety.get_settings.cache_clear()


def test_allows_https_matching_suffix(monkeypatch):
    _set(monkeypatch, "epfl.ch")
    assert url_safety.validate_external_url("https://tableau.epfl.ch/") == (
        "https://tableau.epfl.ch/"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://tableau.epfl.ch/",  # not https
        "https://tableau.evil.com/",  # host not allowed
        "https://evil-epfl.ch/",  # suffix not on a dot boundary
        "https://169.254.169.254/",  # cloud metadata
    ],
)
def test_rejects_unsafe(monkeypatch, url):
    _set(monkeypatch, "epfl.ch")
    with pytest.raises(ValueError):
        url_safety.validate_external_url(url)


def test_fails_closed_when_allowlist_empty(monkeypatch):
    _set(monkeypatch, "")
    with pytest.raises(ValueError):
        url_safety.validate_external_url("https://tableau.epfl.ch/")
