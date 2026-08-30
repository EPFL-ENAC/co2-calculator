"""Postgres fixtures for the read-path statement-budget suite (#2527 task 6).

Self-contained rather than importing the ``data_ingestion`` conftest: those
fixtures hard-code a container name and host port, so a session running both
packages would have the second container clobber the first. Same reasoning —
and same shape — as ``tests/integration/test_alembic_migrations.py``, which
picked its own port for exactly this reason.

Requires Docker.
"""

import time
from collections.abc import Iterator

import docker
import docker.errors
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

# Importing the models registers them with ``SQLModel.metadata`` before
# ``create_all`` runs; ``app.main`` pulls in every model the routes touch.
from app.main import app as _app  # noqa: F401

PG_IMAGE = "postgres:16-alpine"
PG_CONTAINER_NAME = "test-read-path-budget-postgres"
# Not 55432 (data_ingestion conftest), not 55433 (alembic smoke), not a
# host-side dev postgres on 5432.
PG_PORT = 55434
PG_DB = "test_read_path_budget"
PG_USER = "test"
PG_PASSWORD = "test"
PG_READY_MARKER = b"database system is ready to accept connections"
PG_READY_TIMEOUT_S = 60


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[str]:
    """Spin up a Postgres container for the suite; yields its asyncpg URL."""
    client = docker.from_env()
    try:
        try:
            client.containers.get(PG_CONTAINER_NAME).remove(force=True)
        except docker.errors.NotFound:
            pass

        try:
            client.images.get(PG_IMAGE)
        except docker.errors.ImageNotFound:
            client.images.pull(PG_IMAGE)

        container = client.containers.run(
            image=PG_IMAGE,
            name=PG_CONTAINER_NAME,
            ports={"5432/tcp": PG_PORT},
            environment={
                "POSTGRES_DB": PG_DB,
                "POSTGRES_USER": PG_USER,
                "POSTGRES_PASSWORD": PG_PASSWORD,
            },
            detach=True,
            remove=True,
        )

        # Postgres logs the ready marker twice: once during init, once after
        # the final restart. Wait for the second so we don't race init.
        deadline = time.time() + PG_READY_TIMEOUT_S
        while time.time() < deadline:
            container.reload()
            if container.status == "running":
                if container.logs().count(PG_READY_MARKER) >= 2:
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"Postgres container not ready within {PG_READY_TIMEOUT_S}s"
            )

        yield (
            f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}"
        )
    finally:
        try:
            client.containers.get(PG_CONTAINER_NAME).stop(timeout=10)
        except docker.errors.NotFound:
            pass


@pytest_asyncio.fixture(scope="function")
async def pg_dsn(postgres_container: str) -> str:
    """DSN against a freshly-created schema — one clean slate per test."""
    engine = create_async_engine(postgres_container, future=True)
    async with engine.begin() as conn:
        # Mirror migration 3f8147b5e516: the GIN trigram index on
        # locations.keywords needs pg_trgm, and create_all (not Alembic)
        # builds the schema here.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    await engine.dispose()
    return postgres_container
