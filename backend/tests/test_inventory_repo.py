import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.repositories.inventory_repo import InventoryRepository
from app.schemas.inventory import InventoryCreate, InventoryUpdate

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
async def test_create_and_get_inventory(async_session):
    repo = InventoryRepository(async_session)
    data = InventoryCreate(year=2025, unit_id="unit1")
    inv = await repo.create_inventory(data)
    assert inv.id is not None
    fetched = await repo.get_inventory(inv.id)
    assert fetched is not None
    assert fetched.unit_id == "unit1"
    assert fetched.year == 2025


@pytest.mark.asyncio
async def test_list_inventories_by_unit(async_session):
    repo = InventoryRepository(async_session)
    await repo.create_inventory(InventoryCreate(year=2025, unit_id="unitA"))
    await repo.create_inventory(InventoryCreate(year=2025, unit_id="unitA"))
    await repo.create_inventory(InventoryCreate(year=2025, unit_id="unitB"))
    items = await repo.list_inventories_by_unit("unitA")
    assert len(items) == 2


@pytest.mark.asyncio
async def test_update_and_delete_inventory(async_session):
    repo = InventoryRepository(async_session)
    data = InventoryCreate(year=2025, unit_id="unitX")
    inv = await repo.create_inventory(data)
    # Update
    update = InventoryUpdate(year=2026, unit_id="unitX")
    updated = await repo.update_inventory(inv.id, update)
    assert updated.year == 2026
    # Delete
    deleted = await repo.delete_inventory(inv.id)
    assert deleted is True
    assert await repo.get_inventory(inv.id) is None
