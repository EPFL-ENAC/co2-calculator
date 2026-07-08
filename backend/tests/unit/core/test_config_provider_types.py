"""Regression tests for Settings' role/unit provider type config (#1713).

ROLE_PROVIDER_TYPE and UNIT_PROVIDER_TYPE replace the old, overloaded
PROVIDER_PLUGIN env var. Both are required with no default — missing or
invalid config must fail Settings construction at startup, not silently
fall back. Selecting 'accred' on either requires all three
ACCRED_API_* vars (see Settings.validate_accred_config).
"""

import pytest
from pydantic import ValidationError

from app.core.config import RoleProviderType, Settings, UnitProviderType


def test_missing_role_provider_type_fails_startup(monkeypatch):
    monkeypatch.delenv("ROLE_PROVIDER_TYPE", raising=False)
    with pytest.raises(ValidationError):
        Settings(UNIT_PROVIDER_TYPE=UnitProviderType.TEST)


def test_missing_unit_provider_type_fails_startup(monkeypatch):
    monkeypatch.delenv("UNIT_PROVIDER_TYPE", raising=False)
    with pytest.raises(ValidationError):
        Settings(ROLE_PROVIDER_TYPE=RoleProviderType.JWT)


def test_invalid_role_provider_type_fails_startup():
    with pytest.raises(ValidationError):
        Settings(ROLE_PROVIDER_TYPE="bogus", UNIT_PROVIDER_TYPE=UnitProviderType.TEST)


def test_invalid_unit_provider_type_fails_startup():
    with pytest.raises(ValidationError):
        Settings(ROLE_PROVIDER_TYPE=RoleProviderType.JWT, UNIT_PROVIDER_TYPE="bogus")


def test_jwt_and_database_do_not_require_accred_config():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.JWT,
        UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
    )
    assert settings.ACCRED_API_BASE_URL is None


def test_test_provider_types_do_not_require_accred_config():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.TEST,
        UNIT_PROVIDER_TYPE=UnitProviderType.TEST,
    )
    assert settings.ACCRED_API_BASE_URL is None


def test_accred_role_provider_requires_all_three_accred_vars():
    with pytest.raises(ValidationError, match="Missing required Accred config"):
        Settings(
            ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
            UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
        )


def test_accred_unit_provider_requires_all_three_accred_vars():
    with pytest.raises(ValidationError, match="Missing required Accred config"):
        Settings(
            ROLE_PROVIDER_TYPE=RoleProviderType.JWT,
            UNIT_PROVIDER_TYPE=UnitProviderType.ACCRED,
        )


def test_accred_error_lists_missing_vars_only():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
            UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
            ACCRED_API_USERNAME="user",
        )
    message = str(exc_info.value)
    assert "ACCRED_API_BASE_URL" in message
    assert "ACCRED_API_KEY" in message


def test_accred_provider_succeeds_with_all_three_vars():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
        UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
        ACCRED_API_BASE_URL="https://accred.example.com",
        ACCRED_API_USERNAME="user",
        ACCRED_API_KEY="key",
    )
    assert settings.ACCRED_API_BASE_URL == "https://accred.example.com"
