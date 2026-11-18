"""DB_URL has no default, and FRONTEND_URL is checked at boot (#3244).

A deployment that leaves DB_URL out must not boot. An empty value counts as
left out: a Helm value rendered as "" gives ``DB_URL=``. FRONTEND_URL is
read by the app only, so Settings builds without it for alembic and the
scripts, and main.assert_frontend_url stops the app.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_empty_db_url_stops_the_boot(monkeypatch):
    monkeypatch.setenv("DB_URL", "")
    with pytest.raises(ValidationError, match="DB_URL"):
        Settings(_env_file=None)


def test_missing_db_url_stops_the_boot(monkeypatch):
    monkeypatch.delenv("DB_URL", raising=False)
    with pytest.raises(ValidationError, match="DB_URL"):
        Settings(_env_file=None)


# Regression: `make db-migrate` failed on a FRONTEND_URL it never reads.
def test_settings_build_without_frontend_url(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    assert Settings(_env_file=None).FRONTEND_URL == ""
