"""Smoke test: ``make db-create; make db-migrate`` succeeds against real PG.

This guards against regressions where a hand-written migration imports
something that is not resolvable from a clean alembic invocation (e.g.
``from alembic.indexes import …`` resolving to the installed PyPI
``alembic`` package rather than a local helper).

The test spawns its own ``postgres:16-alpine`` testcontainer rather than
reusing the data_ingestion fixture so it stays self-contained and can
be selected by name on PR CI without dragging the rest of the
integration suite in.

It exercises two things end-to-end:

1. ``uv run -m scripts.manage_db --action create`` — equivalent of
   ``make db-create``: creates the target DB on the maintenance ``postgres``
   DB using ``CREATE DATABASE``.
2. ``uv run alembic upgrade head`` — equivalent of ``make db-migrate``:
   applies every migration on a fresh DB.

Why subprocess rather than calling alembic's Python API directly: this
test asserts that the **commands a developer/operator actually runs**
work.  Running through ``uv run`` mirrors the Makefile and catches
packaging-time issues (e.g. missing dependencies, broken entrypoints)
that a Python-side ``command.upgrade(...)`` would not.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import docker
import docker.errors
import pytest

_PG_IMAGE = "postgres:16-alpine"
_PG_CONTAINER_NAME = "test-alembic-migrations-postgres"
# Picked to not collide with the data_ingestion conftest (55432) or any
# host-side dev postgres on 5432.
_PG_PORT = 55433
_PG_USER = "postgres"
_PG_PASSWORD = "postgres"
_PG_MAINTENANCE_DB = "postgres"
_PG_TARGET_DB = "test_alembic_migrations"
_PG_READY_MARKER = b"database system is ready to accept connections"
_PG_READY_TIMEOUT_S = 60

# ``backend/`` — the dir we must ``cwd`` into for ``alembic`` and
# ``uv run -m scripts.manage_db`` to find their configuration.  This
# file lives at backend/tests/integration/test_alembic_migrations.py.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _target_db_url() -> str:
    """DSN for the freshly-created target DB.

    Plain ``postgresql://`` (no driver suffix) — matches the production
    env-var shape and lets ``alembic/env.py`` and ``scripts/manage_db.py``
    each pick the driver they need.  Notably, ``manage_db.py`` only
    rewrites bare ``postgresql`` / ``postgres`` / ``postgresql+psycopg``
    URLs to the sync ``+psycopg`` driver; a URL that already says
    ``+asyncpg`` would bypass that rewrite and fail with ``MissingGreenlet``
    when sync ``create_engine`` tries to use it.
    """
    return (
        f"postgresql://{_PG_USER}:{_PG_PASSWORD}@localhost:{_PG_PORT}/{_PG_TARGET_DB}"
    )


@pytest.fixture(scope="module")
def postgres_container() -> Iterator[dict]:
    """Spin up a Postgres container for the migration smoke test.

    Module-scoped: every test in this file shares one container, but
    each test gets a fresh target DB (see ``fresh_target_db``).  Cheaper
    than re-pulling the image per test.

    Pattern mirrors ``tests/integration/services/data_ingestion/conftest.py``
    so future-readers don't have to context-switch.
    """
    client = docker.from_env()
    container = None
    try:
        try:
            old = client.containers.get(_PG_CONTAINER_NAME)
            old.remove(force=True)
        except docker.errors.NotFound:
            # No stale container to clean up
            pass

        try:
            client.images.get(_PG_IMAGE)
        except docker.errors.ImageNotFound:
            print(f"Pulling Postgres image: {_PG_IMAGE}")
            client.images.pull(_PG_IMAGE)

        container = client.containers.run(
            image=_PG_IMAGE,
            name=_PG_CONTAINER_NAME,
            ports={"5432/tcp": _PG_PORT},
            environment={
                "POSTGRES_DB": _PG_MAINTENANCE_DB,
                "POSTGRES_USER": _PG_USER,
                "POSTGRES_PASSWORD": _PG_PASSWORD,
            },
            detach=True,
            remove=True,
        )

        # Postgres logs the ready marker twice: once during init, once
        # after the final restart.  Wait for the second occurrence so we
        # don't race the init phase.
        deadline = time.time() + _PG_READY_TIMEOUT_S
        while time.time() < deadline:
            container.reload()
            if container.status == "running":
                if container.logs().count(_PG_READY_MARKER) >= 2:
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"Postgres container failed to become ready within "
                f"{_PG_READY_TIMEOUT_S}s"
            )

        yield {"host": "localhost", "port": _PG_PORT}

    finally:
        try:
            c = client.containers.get(_PG_CONTAINER_NAME)
            c.stop(timeout=10)
        except docker.errors.NotFound:
            # Container already gone — nothing to stop
            pass
        except Exception as e:  # pragma: no cover - cleanup best-effort
            print(f"Error stopping postgres container: {e}")


@pytest.fixture()
def alembic_env(postgres_container: dict) -> dict[str, str]:
    """Env dict for alembic / manage_db subprocesses.

    Overrides only ``DB_URL`` and ``DB_NAME``; everything else (OAUTH_*
    etc. from ``pyproject.toml``'s ``pytest-env``) is inherited from
    ``os.environ`` so ``app.core.config.get_settings()`` can instantiate
    when ``alembic/env.py`` imports it.
    """
    env = os.environ.copy()
    env["DB_URL"] = _target_db_url()
    env["DB_NAME"] = _PG_TARGET_DB
    return env


def _run(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    """Run ``cmd`` from ``backend/`` and surface stdout/stderr on failure.

    Captures output so passing tests stay quiet; on failure pytest
    prints the full subprocess output in the assertion message — which
    is exactly what a developer running ``make db-migrate`` sees.
    """
    return subprocess.run(
        cmd,
        cwd=_BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _drop_target_db(env: dict[str, str]) -> None:
    """Best-effort drop of the target DB on the maintenance DB.

    Used between subtests so each starts from "DB does not exist", which
    is the exact precondition ``make db-create`` is designed for.  The
    target DB might not exist (first subtest), so we tolerate failure.
    """
    drop_env = env.copy()
    # ``manage_db --action drop`` already targets the maintenance DB
    # internally, so just call it; its Makefile target tolerates failure
    # ("|| true") for the same reason.
    _run(["uv", "run", "-m", "scripts.manage_db", "--action", "drop"], drop_env)


def test_make_db_create_then_db_migrate(alembic_env: dict[str, str]) -> None:
    """Equivalent of ``make db-create && make db-migrate`` on a fresh DB.

    This is the exact sequence the user runs locally; we just point
    ``DB_URL`` at a throwaway postgres container.
    """
    _drop_target_db(alembic_env)

    create = _run(
        ["uv", "run", "-m", "scripts.manage_db", "--action", "create"],
        alembic_env,
    )
    assert create.returncode == 0, (
        f"`make db-create` equivalent failed:\n"
        f"stdout:\n{create.stdout}\nstderr:\n{create.stderr}"
    )

    migrate = _run(["uv", "run", "alembic", "upgrade", "head"], alembic_env)
    assert migrate.returncode == 0, (
        f"`make db-migrate` (alembic upgrade head) failed:\n"
        f"stdout:\n{migrate.stdout}\nstderr:\n{migrate.stderr}"
    )


# revision 95fe938000d4 (#2458): deletes orphaned NULL-created_by
# Simulator_Explore projects. Migrated to just before it, seed one orphaned
# project tree + one normal one, apply it, assert only the orphaned tree is
# gone.
_PRE_2458_REVISION = "6e32aa42f6f4"


def _seed_2458_fixture(db_url: str) -> dict[str, int]:
    """Seed one NULL-created_by (orphaned) and one normal Simulator_Explore
    project, each with a full report/module/data-entry tree, plus a
    Calculator project (unaffected — different report type, must survive
    regardless of created_by) to prove the type filter isn't a no-op.

    Plain sync psycopg + raw SQL, deliberately not the async ORM session
    used by the app: mixing ``asyncio.run()`` calls with SQLAlchemy's
    asyncpg/greenlet bridge inside a sync pytest-asyncio test reliably hit
    ``MissingGreenlet`` here, for reasons orthogonal to the migration this
    is testing — sync sidesteps that class of bug entirely.

    Returns the ids the test needs to check afterward.
    """
    from sqlalchemy import create_engine, text

    sync_url = db_url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            unit_id = conn.execute(
                text(
                    "INSERT INTO units"
                    " (provider, institutional_code, name, level, is_active)"
                    " VALUES ('TEST'::user_provider_enum, 'U2458',"
                    " 'Migration test unit', 1, true) RETURNING id"
                )
            ).scalar_one()
            user_id = conn.execute(
                text(
                    "INSERT INTO users (institutional_id, provider, email)"
                    " VALUES ('U2458-user', 'TEST'::user_provider_enum,"
                    " 'u2458@example.test') RETURNING id"
                )
            ).scalar_one()

            def _project(created_by: int | None, report_type: str) -> int:
                return conn.execute(
                    text(
                        "INSERT INTO carbon_projects"
                        " (unit_id, carbon_report_type, created_by,"
                        " is_viewable_by_unit_members)"
                        " VALUES (:unit_id,"
                        " CAST(:report_type AS carbon_report_type_enum),"
                        " :created_by, false) RETURNING id"
                    ),
                    {
                        "unit_id": unit_id,
                        "report_type": report_type,
                        "created_by": created_by,
                    },
                ).scalar_one()

            project_ids = {
                "orphaned": _project(None, "Simulator_Explore"),
                "normal": _project(user_id, "Simulator_Explore"),
                "calculator": _project(None, "Calculator"),
            }

            ids: dict[str, int] = {"unit_id": unit_id}
            for label, project_id in project_ids.items():
                report_id = conn.execute(
                    text(
                        "INSERT INTO carbon_reports"
                        " (year, unit_id, carbon_project_id, overall_status)"
                        " VALUES (2026, :unit_id, :project_id, 0) RETURNING id"
                    ),
                    {"unit_id": unit_id, "project_id": project_id},
                ).scalar_one()
                module_id = conn.execute(
                    text(
                        "INSERT INTO carbon_report_modules"
                        " (module_type_id, carbon_report_id, status)"
                        " VALUES (1, :report_id, 0) RETURNING id"
                    ),
                    {"report_id": report_id},
                ).scalar_one()
                entry_id = conn.execute(
                    text(
                        "INSERT INTO data_entries"
                        " (data_entry_type_id, carbon_report_module_id, data,"
                        " created_at, updated_at)"
                        " VALUES (1, :module_id, '{}'::jsonb, now(), now())"
                        " RETURNING id"
                    ),
                    {"module_id": module_id},
                ).scalar_one()
                ids[f"{label}_project_id"] = project_id
                ids[f"{label}_report_id"] = report_id
                ids[f"{label}_module_id"] = module_id
                ids[f"{label}_entry_id"] = entry_id

            # Sanity: exactly what we think we seeded, nothing more (this
            # unit is fresh, so a plain count is unambiguous).
            count = conn.execute(
                text("SELECT count(*) FROM carbon_projects WHERE unit_id = :unit_id"),
                {"unit_id": unit_id},
            ).scalar_one()
            assert count == 3, f"expected 3 seeded projects, found {count}"

        return ids
    finally:
        engine.dispose()


def _assert_2458_cleanup(db_url: str, ids: dict[str, int]) -> None:
    from sqlalchemy import create_engine, text

    sync_url = db_url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(sync_url)
    table_by_kind = {
        "project": "carbon_projects",
        "report": "carbon_reports",
        "module": "carbon_report_modules",
        "entry": "data_entries",
    }
    try:
        with engine.connect() as conn:

            def _exists(table: str, row_id: int) -> bool:
                result = conn.execute(
                    text(f"SELECT 1 FROM {table} WHERE id = :id"),  # noqa: S608
                    {"id": row_id},
                )
                return result.first() is not None

            for label in ("orphaned",):
                for kind, table in table_by_kind.items():
                    assert not _exists(table, ids[f"{label}_{kind}_id"]), (
                        f"{label} {kind} should have been deleted"
                    )
            for label in ("normal", "calculator"):
                for kind, table in table_by_kind.items():
                    assert _exists(table, ids[f"{label}_{kind}_id"]), (
                        f"{label} {kind} should have survived"
                    )
    finally:
        engine.dispose()


def test_2458_orphaned_explore_cleanup(alembic_env: dict[str, str]) -> None:
    """#2458: only the NULL-created_by Simulator_Explore tree is deleted.

    A same-typed but non-orphaned Explore project, and a NULL-created_by
    Calculator project (created_by is legitimately unset for Calculator —
    the column only means something for Explore/Plan), must both survive.
    """
    _drop_target_db(alembic_env)
    create = _run(
        ["uv", "run", "-m", "scripts.manage_db", "--action", "create"],
        alembic_env,
    )
    assert create.returncode == 0, create.stderr

    pre = _run(
        ["uv", "run", "alembic", "upgrade", _PRE_2458_REVISION],
        alembic_env,
    )
    assert pre.returncode == 0, (
        f"upgrade to {_PRE_2458_REVISION} (just before #2458) failed:\n"
        f"{pre.stdout}\n{pre.stderr}"
    )

    db_url = alembic_env["DB_URL"]
    ids = _seed_2458_fixture(db_url)

    migrate = _run(["uv", "run", "alembic", "upgrade", "head"], alembic_env)
    assert migrate.returncode == 0, (
        f"upgrade to head (applying #2458) failed:\n{migrate.stdout}\n{migrate.stderr}"
    )

    _assert_2458_cleanup(db_url, ids)
