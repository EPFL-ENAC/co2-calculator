"""Test configuration for pytest."""

import logging
from datetime import datetime
from itertools import count

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.unit import Unit
from app.models.unit_user import UnitUser
from app.models.user import RoleName, User, UserProvider

# Test database URL (use in-memory SQLite for tests)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Auto-incrementing counters for unique default values
# ---------------------------------------------------------------------------
_seq_unit = count(1)
_seq_user = count(1)


def pytest_configure():
    """Configure pytest settings if needed."""
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Core DB session fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database for each test."""
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Model factory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_unit():
    """Factory for Unit model instances.

    Returns an async callable that creates, flushes, and returns a Unit.
    Usage::

        unit = await make_unit(db_session, name="LCBM")
    """

    async def _make(session: AsyncSession, **overrides) -> Unit:
        n = next(_seq_unit)
        defaults = dict(
            provider=UserProvider.DEFAULT,
            institutional_code=f"CODE-{n}",
            institutional_id=f"CF-{n}",
            name=f"Unit-{n}",
            level=2,
            is_active=True,
        )
        defaults.update(overrides)
        unit = Unit(**defaults)
        session.add(unit)
        await session.flush()
        return unit

    return _make


@pytest.fixture
def make_user():
    """Factory for User model instances."""

    async def _make(session: AsyncSession, **overrides) -> User:
        n = next(_seq_user)
        defaults = dict(
            institutional_id=f"SCIPER-{n}",
            provider=UserProvider.DEFAULT,
            email=f"user{n}@test.local",
            display_name=f"Test User {n}",
        )
        defaults.update(overrides)
        user = User(**defaults)
        session.add(user)
        await session.flush()
        return user

    return _make


@pytest.fixture
def make_unit_user():
    """Factory for UnitUser association."""

    async def _make(
        session: AsyncSession,
        unit_id: int,
        user_id: int,
        role: RoleName = RoleName.CO2_USER_STD,
    ) -> UnitUser:
        uu = UnitUser(unit_id=unit_id, user_id=user_id, role=role)
        session.add(uu)
        await session.flush()
        return uu

    return _make


@pytest.fixture
def make_carbon_report():
    """Factory for CarbonReport model instances."""

    async def _make(session: AsyncSession, **overrides) -> CarbonReport:
        defaults = dict(
            year=2024,
            unit_id=1,
            overall_status=ModuleStatus.NOT_STARTED,
        )
        defaults.update(overrides)
        cr = CarbonReport(**defaults)
        session.add(cr)
        await session.flush()
        return cr

    return _make


@pytest.fixture
def make_carbon_report_module():
    """Factory for CarbonReportModule model instances."""

    async def _make(session: AsyncSession, **overrides) -> CarbonReportModule:
        defaults = dict(
            module_type_id=1,
            status=ModuleStatus.NOT_STARTED,
            carbon_report_id=1,
        )
        defaults.update(overrides)
        crm = CarbonReportModule(**defaults)
        session.add(crm)
        await session.flush()
        return crm

    return _make


@pytest.fixture
def make_data_entry():
    """Factory for DataEntry model instances."""

    async def _make(session: AsyncSession, **overrides) -> DataEntry:
        defaults = dict(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=1,
            data={},
            status=DataEntryStatusEnum.PENDING,
        )
        defaults.update(overrides)
        de = DataEntry(**defaults)
        session.add(de)
        await session.flush()
        return de

    return _make


@pytest.fixture
def make_factor():
    """Factory for Factor model instances."""

    async def _make(session: AsyncSession, **overrides) -> Factor:
        defaults = dict(
            emission_type_id=EmissionType.food.value,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            classification={},
            values={"kg_co2eq_per_fte": 420.0},
            year=2024,
        )
        defaults.update(overrides)
        f = Factor(**defaults)
        session.add(f)
        await session.flush()
        return f

    return _make


@pytest.fixture
def make_data_entry_emission():
    """Factory for DataEntryEmission model instances."""

    async def _make(session: AsyncSession, **overrides) -> DataEntryEmission:
        defaults = dict(
            data_entry_id=1,
            emission_type_id=EmissionType.food.value,
            primary_factor_id=None,
            kg_co2eq=100.0,
            meta={},
            computed_at=datetime.utcnow(),
        )
        defaults.update(overrides)
        dee = DataEntryEmission(**defaults)
        session.add(dee)
        await session.flush()
        return dee

    return _make


# ---------------------------------------------------------------------------
# Policy mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_policy_allow(monkeypatch):
    """Mock OPA to always allow with no filters."""

    async def mock_query_policy(*args, **kwargs):
        """Async mock for OPA query."""
        return {"allow": True, "filters": {"unit_ids": ["12345"]}}

    monkeypatch.setattr("app.services.resource_service.query_policy", mock_query_policy)
    return mock_query_policy


@pytest.fixture
def mock_policy_deny(monkeypatch):
    """Mock OPA to always deny."""

    async def mock_query_policy(*args, **kwargs):
        """Async mock for OPA query."""
        return {"allow": False, "reason": "Access denied"}

    monkeypatch.setattr("app.services.resource_service.query_policy", mock_query_policy)
    return mock_query_policy
