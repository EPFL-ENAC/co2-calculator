import pytest

from app.core import crypto
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _restore_settings_cache():
    """Clear the lru_cache after each test too, so once monkeypatch reverts
    the env, the next caller re-reads real settings instead of the blanked
    values left behind by a fail-closed test."""
    yield
    get_settings.cache_clear()


def test_round_trip(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "dev-key-material-please-change")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "dev-salt-please-change")
    crypto.get_settings.cache_clear()  # settings are lru_cached
    token = crypto.encrypt_secret("super-secret-value")
    assert token != "super-secret-value"
    assert crypto.decrypt_secret(token) == "super-secret-value"


def test_fails_closed_without_key(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_SALT", "")
    crypto.get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        crypto.encrypt_secret("x")
