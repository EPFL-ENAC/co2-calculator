"""Test configuration for pytest."""

import logging

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Test database URL (use in-memory SQLite for tests)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def pytest_configure():
    """Configure pytest settings if needed."""
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database for each test."""
    # Create a new engine for each test
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Create session factory and session using SQLModel's AsyncSession
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    # Dispose the engine to clean up connections
    await engine.dispose()


@pytest.fixture
def mock_policy_allow(monkeypatch):
    """Mock OPA to always allow with no filters."""

    async def mock_query_policy(*args, **kwargs):
        """Async mock for OPA query."""
        return {"allow": True, "filters": {"unit_ids": ["12345"]}}

    # Patch it in the resource_service module where it's being called
    monkeypatch.setattr("app.services.resource_service.query_policy", mock_query_policy)
    return mock_query_policy


@pytest.fixture
def mock_policy_deny(monkeypatch):
    """Mock OPA to always deny."""
    # import app.core.opa_client as opa_client

    async def mock_query_policy(*args, **kwargs):
        """Async mock for OPA query."""
        return {"allow": False, "reason": "Access denied"}

    # monkeypatch.setattr(opa_client, "query_opa", mock_query_opa)
    monkeypatch.setattr("app.services.resource_service.query_policy", mock_query_policy)

    return mock_query_policy
