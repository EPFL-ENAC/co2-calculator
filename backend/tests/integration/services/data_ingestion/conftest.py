"""Postgres testcontainer fixtures for data_ingestion integration tests.

Spins up a real Postgres container so we can exercise behavior in-memory
SQLite cannot — partial unique indexes tripping under concurrency, true
transactional semantics, JSONB ordering, etc.

Patterned on ``tests/integration/es_integration/conftest.py``.
"""

import time

import docker
import docker.errors
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Ensure every model class is registered with SQLModel.metadata before
# create_all runs.  Top-level tests/conftest.py imports many of these for
# the SQLite suite; we re-import here to be self-contained.
from app.models import data_ingestion  # noqa: F401

PG_IMAGE = "postgres:16-alpine"
PG_CONTAINER_NAME = "test-data-ingestion-postgres"
PG_PORT = 55432
PG_DB = "test_data_ingestion"
PG_USER = "test"
PG_PASSWORD = "test"
PG_READY_MARKER = b"database system is ready to accept connections"


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.fixture(scope="session")
def postgres_container(docker_client):
    """Spin up a Postgres container for the test session."""
    container = None
    try:
        try:
            old = docker_client.containers.get(PG_CONTAINER_NAME)
            old.remove(force=True)
        except docker.errors.NotFound:
            pass

        try:
            docker_client.images.get(PG_IMAGE)
        except docker.errors.ImageNotFound:
            print(f"Pulling Postgres image: {PG_IMAGE}")
            docker_client.images.pull(PG_IMAGE)

        container = docker_client.containers.run(
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
        # the final restart.  Wait for the second occurrence.
        timeout = 60
        deadline = time.time() + timeout
        while time.time() < deadline:
            container.reload()
            if container.status == "running":
                if container.logs().count(PG_READY_MARKER) >= 2:
                    print("Postgres container is ready!")
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"Postgres container failed to become ready within {timeout}s"
            )

        url = (
            f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}"
        )
        yield {"url": url, "container": container}

    finally:
        try:
            c = docker_client.containers.get(PG_CONTAINER_NAME)
            c.stop(timeout=10)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            print(f"Error stopping postgres container: {e}")


@pytest_asyncio.fixture(scope="function")
async def pg_dsn(postgres_container):
    """Function-scoped DSN against a freshly-created schema.

    Drops and re-creates all SQLModel tables before yielding so each test
    starts from a clean slate.  Tests that need their own engines (e.g.
    concurrency tests with one engine per simulated pod) use this DSN.
    """
    url = postgres_container["url"]
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    await engine.dispose()
    yield url


@pytest_asyncio.fixture(scope="function")
async def pg_session(pg_dsn):
    """Function-scoped AsyncSession against the fresh schema."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
