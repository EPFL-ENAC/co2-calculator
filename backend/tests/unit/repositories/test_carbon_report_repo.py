import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.repositories.carbon_report_repo import CarbonReportRepository
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportUpdate

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_carbon_report(async_session):
    repo = CarbonReportRepository(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await repo.create(data)
    assert inv.id is not None
    fetched = await repo.get(inv.id)
    assert fetched is not None
    assert fetched.unit_id == 1
    assert fetched.year == 2025


@pytest.mark.asyncio
async def test_list_inventories_by_unit(async_session):
    repo = CarbonReportRepository(async_session)
    await repo.create(CarbonReportCreate(year=2025, unit_id=1))
    await repo.create(CarbonReportCreate(year=2025, unit_id=1))
    await repo.create(CarbonReportCreate(year=2025, unit_id=2))
    items = await repo.list_by_unit(1)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_update_and_delete_carbon_report(async_session):
    repo = CarbonReportRepository(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await repo.create(data)
    # Update
    update = CarbonReportUpdate(year=2026, unit_id=1)
    updated = await repo.update(inv.id, update)
    assert updated.year == 2026
    # Delete
    deleted = await repo.delete(inv.id)
    assert deleted is True
    assert await repo.get(inv.id) is None
