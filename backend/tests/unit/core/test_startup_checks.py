"""Unit tests for the boot-time security gate in `app.main`.

`assert_security_settings` is the fail-closed check that stops the app from
booting on stage/prod if credential-encryption or SSRF-allowlist settings are
missing. It only does attribute access on its argument, so a
`types.SimpleNamespace` stands in for `Settings` without needing the full
pydantic-settings machinery.
"""

from types import SimpleNamespace

import pytest

from app.main import (
    assert_poller_isolation,
    assert_proxy_trust_settings,
    assert_security_settings,
)


def _settings(**overrides) -> SimpleNamespace:
    defaults = {
        "LOCAL_ENVIRONMENT": False,
        "JWT_HMAC_KEY": "jwt-key",
        "SESSION_HMAC_KEY": "session-key",
        "CREDENTIALS_ENCRYPTION_KEY": "key",
        "CREDENTIALS_ENCRYPTION_SALT": "salt",
        "CONNECTOR_ALLOWED_HOST_SUFFIXES": "epfl.ch",
        "FILES_ENCRYPTION_KEY": "files-key",
        "FILES_ENCRYPTION_SALT": "files-salt",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_local_environment_skips_check_even_if_all_empty():
    settings = _settings(
        LOCAL_ENVIRONMENT=True,
        CREDENTIALS_ENCRYPTION_KEY="",
        CREDENTIALS_ENCRYPTION_SALT="",
        CONNECTOR_ALLOWED_HOST_SUFFIXES="",
        FILES_ENCRYPTION_KEY="",
        FILES_ENCRYPTION_SALT="",
    )
    assert_security_settings(settings)  # must not raise


@pytest.mark.parametrize(
    "missing_field",
    [
        "JWT_HMAC_KEY",
        "SESSION_HMAC_KEY",
        "CREDENTIALS_ENCRYPTION_KEY",
        "CREDENTIALS_ENCRYPTION_SALT",
        "CONNECTOR_ALLOWED_HOST_SUFFIXES",
        "FILES_ENCRYPTION_KEY",
        "FILES_ENCRYPTION_SALT",
    ],
)
def test_non_local_raises_when_a_required_setting_is_empty(missing_field):
    settings = _settings(**{missing_field: ""})
    with pytest.raises(RuntimeError) as exc:
        assert_security_settings(settings)
    assert missing_field in str(exc.value)


def test_non_local_passes_when_all_required_settings_set():
    settings = _settings()
    assert_security_settings(settings)  # must not raise


# --- assert_poller_isolation (#2220) -------------------------------------
#
# Root cause of #2220's "Failed to move file" failures: a laptop running
# `make dev` with `.env` pointed at the shared dev DB polled and claimed
# dev's ingestion jobs, then resolved their uploaded files against its own
# LocalFilesStore. The guard refuses to boot a LOCAL_ENVIRONMENT instance
# whose poller would claim jobs from a non-local database.


def _poller_settings(**overrides) -> SimpleNamespace:
    defaults = {
        "LOCAL_ENVIRONMENT": True,
        "RUN_BACKGROUND_POLLER": True,
        "DB_URL": "postgresql+asyncpg://app:pw@localhost:5432/app",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_local_poller_against_shared_db_refuses_to_boot():
    settings = _poller_settings(
        DB_URL="postgresql://app:pw@co2-dev.postgresql.dbaas.intranet.epfl.ch:5432/app"
    )
    with pytest.raises(RuntimeError) as exc:
        assert_poller_isolation(settings)
    assert "co2-dev.postgresql.dbaas.intranet.epfl.ch" in str(exc.value)
    assert "RUN_BACKGROUND_POLLER" in str(exc.value)


@pytest.mark.parametrize(
    "db_url",
    [
        "postgresql+asyncpg://app:pw@localhost:5432/app",
        "postgresql://app:pw@127.0.0.1:5432/app",
        "postgresql://app:pw@postgres:5432/app",  # docker-compose service
        "sqlite+aiosqlite:///./co2_calculator.db",  # no host at all
    ],
)
def test_local_poller_against_local_db_boots(db_url):
    assert_poller_isolation(_poller_settings(DB_URL=db_url))  # must not raise


def test_shared_db_allowed_when_poller_disabled():
    settings = _poller_settings(
        RUN_BACKGROUND_POLLER=False,
        DB_URL="postgresql://app:pw@co2-dev.postgresql.dbaas.intranet.epfl.ch:5432/app",
    )
    assert_poller_isolation(settings)  # must not raise


def test_deployed_pods_are_exempt():
    # Pods legitimately poll a remote DB; the guard is local-only.
    settings = _poller_settings(
        LOCAL_ENVIRONMENT=False,
        DB_URL="postgresql://app:pw@co2-dev.postgresql.dbaas.intranet.epfl.ch:5432/app",
    )
    assert_poller_isolation(settings)  # must not raise


# --- assert_proxy_trust_settings (#2530) ---------------------------------


def test_trusting_every_proxy_refuses_to_boot(monkeypatch):
    """'*' makes uvicorn take the client-chosen first X-Forwarded-For element
    instead of walking the chain — the exact forgery #2530 removed.
    """
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    with pytest.raises(RuntimeError, match="FORWARDED_ALLOW_IPS"):
        assert_proxy_trust_settings()


def test_real_proxy_cidrs_boot(monkeypatch):
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.20.0.0/16,10.98.42.0/24")
    assert_proxy_trust_settings()  # must not raise


def test_unset_forwarded_allow_ips_boots(monkeypatch):
    """Uvicorn's own default is 127.0.0.1 — trust nothing. Local dev and any
    env that has not configured a proxy must still start.
    """
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    assert_proxy_trust_settings()  # must not raise


@pytest.mark.parametrize("wildcard", ["0.0.0.0/0", "::/0", "10.20.0.0/16,0.0.0.0/0"])
def test_a_zero_prefix_network_refuses_to_boot(monkeypatch, wildcard):
    """The second spelling of "trust everything", and the one a guard that
    only greps for '*' would wave through.

    uvicorn sets ``always_trust`` on '*' alone, so ``0.0.0.0/0`` takes the
    other path: every address is a trusted network, the reverse walk finds no
    untrusted hop, and ``get_trusted_client_address`` falls through to the
    same client-chosen leftmost element. Same forgery, different config.
    """
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", wildcard)
    with pytest.raises(RuntimeError, match="FORWARDED_ALLOW_IPS"):
        assert_proxy_trust_settings()
