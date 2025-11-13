"""Test configuration for pytest."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app

# Test database URL (use in-memory SQLite for tests)
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

# Create async test engine
engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    echo=True,  # Optional: see SQL queries
)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Create a test client with overridden database dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup():
    """Cleanup after each test."""
    yield
    # Cleanup code if needed


@pytest.fixture
def mock_opa_allow(monkeypatch):
    """Mock OPA to always allow with no filters."""

    async def mock_query_opa(*args, **kwargs):
        """Async mock for OPA query."""
        return {"allow": True, "filters": {}}

    # Patch it in the resource_service module where it's being called
    monkeypatch.setattr("app.services.resource_service.query_opa", mock_query_opa)
    return mock_query_opa


@pytest.fixture
def mock_opa_deny(monkeypatch):
    """Mock OPA to always deny."""
    # import app.core.opa_client as opa_client

    async def mock_query_opa(*args, **kwargs):
        """Async mock for OPA query."""
        return {"allow": False, "reason": "Access denied"}

    # monkeypatch.setattr(opa_client, "query_opa", mock_query_opa)
    monkeypatch.setattr("app.services.resource_service.query_opa", mock_query_opa)

    return mock_query_opa
