"""Test configuration for pytest."""

import logging
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_db
from app.main import app
from app.models.factor import Factor

# Test database URL (use in-memory SQLite for tests)
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

# Create async test engine
engine = create_async_engine(
    TEST_DB_URL,
    pool_pre_ping=True,
    echo=True,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def pytest_configure():
    """Configure pytest settings if needed."""
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database for each test."""

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


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


# Constants for global reference data (matches migration)
GLOBAL_MODULE_TYPE_ID = 99
ENERGY_MIX_DATA_ENTRY_TYPE_ID = 100


@pytest_asyncio.fixture
async def emission_factor_ch(db_session: AsyncSession) -> Factor:
    """Create Swiss electricity emission factor in unified factors table.

    Use this fixture for tests that need emission factors.
    The factor is stored in the factors table with factor_family='emission'.
    """
    factor = Factor(
        factor_family="emission",
        data_entry_type_id=ENERGY_MIX_DATA_ENTRY_TYPE_ID,
        classification={
            "region": "CH",
            "factor_name": "swiss_electricity_mix",
        },
        values={
            "kg_co2eq_per_kwh": 0.128,
        },
        value_units={
            "kg_co2eq_per_kwh": "kgCO2eq/kWh",
        },
        version=1,
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
        source="Swiss Federal Office of Energy (SFOE)",
        meta={
            "description": "Swiss electricity consumption mix",
        },
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor


@pytest_asyncio.fixture
async def emission_factor_eu(db_session: AsyncSession) -> Factor:
    """Create EU electricity emission factor in unified factors table."""
    factor = Factor(
        factor_family="emission",
        data_entry_type_id=ENERGY_MIX_DATA_ENTRY_TYPE_ID,
        classification={
            "region": "EU",
            "factor_name": "eu_electricity_mix",
        },
        values={
            "kg_co2eq_per_kwh": 0.275,
        },
        value_units={
            "kg_co2eq_per_kwh": "kgCO2eq/kWh",
        },
        version=1,
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
        source="European Environment Agency",
        meta={
            "description": "EU average electricity consumption mix",
        },
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor
