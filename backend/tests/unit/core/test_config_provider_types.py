"""Regression tests for Settings' role/unit provider type config (#1713).

ROLE_PROVIDER_TYPE and UNIT_PROVIDER_TYPE replace the old, overloaded
PROVIDER_PLUGIN env var. Both are required with no default — missing or
invalid config must fail Settings construction at startup, not silently
fall back. Selecting 'accred' on either requires all three ACCRED_API_*
vars at app boot (assert_accred_settings in app/main.py) — but NOT at
Settings construction, so non-app contexts like alembic migrations can
build Settings without Accred credentials.
"""

import pytest
from pydantic import ValidationError

from app.core.config import RoleProviderType, Settings, UnitProviderType
from app.main import assert_accred_settings


@pytest.fixture(autouse=True)
def _no_local_dotenv(monkeypatch, tmp_path):
    # Settings(env_file=".env") reads the real backend/.env when cwd points
    # at it, so a developer's local Accred config can silently satisfy
    # fields these tests expect to be missing. Run from an empty dir instead.
    monkeypatch.chdir(tmp_path)


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


def test_accred_settings_construct_without_creds_for_non_app_contexts():
    # Regression: alembic migrations build Settings with the app's env
    # (provider type 'accred') but must not need Accred credentials.
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
        UNIT_PROVIDER_TYPE=UnitProviderType.ACCRED,
    )
    assert settings.ACCRED_API_BASE_URL is None


def test_accred_role_provider_requires_all_three_accred_vars_at_boot():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
        UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
    )
    with pytest.raises(RuntimeError, match="Missing required Accred config"):
        assert_accred_settings(settings)


def test_accred_unit_provider_requires_all_three_accred_vars_at_boot():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.JWT,
        UNIT_PROVIDER_TYPE=UnitProviderType.ACCRED,
    )
    with pytest.raises(RuntimeError, match="Missing required Accred config"):
        assert_accred_settings(settings)


def test_accred_boot_error_lists_missing_vars_only():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
        UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
        ACCRED_API_USERNAME="user",
    )
    with pytest.raises(RuntimeError) as exc_info:
        assert_accred_settings(settings)
    message = str(exc_info.value)
    assert "ACCRED_API_BASE_URL" in message
    assert "ACCRED_API_KEY" in message
    assert "ACCRED_API_USERNAME" not in message


def test_dotenv_db_url_overrides_stray_shell_env_var(monkeypatch, tmp_path):
    # Regression: a leftover `export DB_URL=...` in a dev's shell must not
    # silently outrank a `.env` the dev just fixed. .env wins locally;
    # stage/prod ship no .env file so real env vars still apply there.
    monkeypatch.setenv("DB_URL", "postgresql://from-shell-env/db")
    (tmp_path / ".env").write_text("DB_URL=postgresql://from-dotenv/db\n")

    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.JWT,
        UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
    )

    assert settings.DB_URL == "postgresql://from-dotenv/db"


def test_accred_provider_succeeds_with_all_three_vars():
    settings = Settings(
        ROLE_PROVIDER_TYPE=RoleProviderType.ACCRED,
        UNIT_PROVIDER_TYPE=UnitProviderType.DATABASE,
        ACCRED_API_BASE_URL="https://accred.example.com",
        ACCRED_API_USERNAME="user",
        ACCRED_API_KEY="key",
    )
    assert_accred_settings(settings)
    assert settings.ACCRED_API_BASE_URL == "https://accred.example.com"
