"""``scripts.manage_db`` refuses shared hosts unless told in so many words.

Regression for 2026-09-08: an integration test spawned ``manage_db --action
drop`` while ``backend/.env`` pointed at prod, and ``.env`` then won over the
environment in this repo's settings, so prod was dropped.
"""

from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from scripts.manage_db import refuse_remote_host


def test_dotenv_cannot_reach_settings_under_pytest() -> None:
    """RC2 #2684: conftest blanks env_file, but get_settings() is lru_cached and
    conftest's own `app.*` imports populate it first. Without the cache_clear()
    in pytest_configure, a dev's real .env (live S3 creds) is live in the test
    process and make_files_store() returns S3FilesStore.

    Only fails without the fix on a machine with a populated `.env` — it is
    green on CI either way, which is exactly the blind spot that let RC2 live.
    Do not engineer around that by writing a `.env` into the repo root here.
    """
    assert Settings.model_config["env_file"] is None
    settings = get_settings()
    assert not settings.S3_ENDPOINT_HOSTNAME
    assert not settings.S3_ACCESS_KEY_ID
    assert not settings.S3_SECRET_ACCESS_KEY


def test_env_var_beats_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A one-off ``DB_URL=... uv run ...`` must outrank the file (#1153 reverted)."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("DB_URL=postgresql://app:x@co2-prod.dbaas.intranet.epfl.ch/app\n")
    local = "postgresql://app:x@localhost:55433/throwaway"
    monkeypatch.setenv("DB_URL", local)
    assert Settings(_env_file=dotenv).DB_URL == local


@pytest.mark.parametrize(
    "db_url",
    [
        "postgresql://app:x@localhost:5432/app",
        "postgresql://app:x@127.0.0.1:55433/test_alembic_migrations",
        "postgresql+psycopg://app:x@db:5432/app",
        "sqlite+aiosqlite:///./test.db",
    ],
)
def test_local_hosts_pass(db_url: str) -> None:
    refuse_remote_host(db_url, allow_remote=False)


def test_remote_host_refused_unless_allowed() -> None:
    remote = "postgresql://app:x@co2-prod.postgresql.dbaas.intranet.epfl.ch:5432/app"
    with pytest.raises(SystemExit, match="co2-prod.postgresql.dbaas"):
        refuse_remote_host(remote, allow_remote=False)
    refuse_remote_host(remote, allow_remote=True)
