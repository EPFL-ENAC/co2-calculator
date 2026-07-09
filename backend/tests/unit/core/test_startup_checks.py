"""Unit tests for the boot-time security gate in `app.main`.

`assert_security_settings` is the fail-closed check that stops the app from
booting on stage/prod if credential-encryption or SSRF-allowlist settings are
missing. It only does attribute access on its argument, so a
`types.SimpleNamespace` stands in for `Settings` without needing the full
pydantic-settings machinery.
"""

from types import SimpleNamespace

import pytest

from app.main import assert_security_settings


def _settings(**overrides) -> SimpleNamespace:
    defaults = {
        "LOCAL_ENVIRONMENT": False,
        "CREDENTIALS_ENCRYPTION_KEY": "key",
        "CREDENTIALS_ENCRYPTION_SALT": "salt",
        "CONNECTOR_ALLOWED_HOST_SUFFIXES": "epfl.ch",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_local_environment_skips_check_even_if_all_empty():
    settings = _settings(
        LOCAL_ENVIRONMENT=True,
        CREDENTIALS_ENCRYPTION_KEY="",
        CREDENTIALS_ENCRYPTION_SALT="",
        CONNECTOR_ALLOWED_HOST_SUFFIXES="",
    )
    assert_security_settings(settings)  # must not raise


@pytest.mark.parametrize(
    "missing_field",
    [
        "CREDENTIALS_ENCRYPTION_KEY",
        "CREDENTIALS_ENCRYPTION_SALT",
        "CONNECTOR_ALLOWED_HOST_SUFFIXES",
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
