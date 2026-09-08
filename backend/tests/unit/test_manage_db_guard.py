"""``scripts.manage_db`` refuses shared hosts unless told in so many words.

Regression for 2026-09-08: an integration test spawned ``manage_db --action
drop`` while ``backend/.env`` pointed at prod, and ``.env`` wins over the
environment in this repo's settings, so prod was dropped.
"""

import pytest

from scripts.manage_db import refuse_remote_host


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
