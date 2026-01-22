import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.constants import ALL_MODULE_TYPE_IDS, ModuleStatus
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportUpdate
from app.services.carbon_report_service import CarbonReportService

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Seed module_types table (required for auto-creating carbon_report modules)
        await conn.execute(
            text(
                """
                INSERT INTO module_types (id, name) VALUES
                (1, 'my-lab'),
                (2, 'professional-travel'),
                (3, 'infrastructure'),
                (4, 'equipment-electric-consumption'),
                (5, 'purchase'),
                (6, 'internal-services'),
                (7, 'external-cloud')
                """
            )
        )
    async_session = sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_service_create_and_get(async_session):
    service = CarbonReportService(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await service.create(data)
    assert inv.id is not None
    fetched = await service.get(inv.id)
    assert fetched is not None
    assert fetched.unit_id == 1
    assert fetched.year == 2025


@pytest.mark.asyncio
async def test_service_create_auto_creates_modules(async_session):
    """Test that creating an carbon_report auto-creates all module records."""
    service = CarbonReportService(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await service.create(data)

    # Check that modules were auto-created
    modules = await service.module_service.list_modules(inv.id)
    assert len(modules) == len(ALL_MODULE_TYPE_IDS)

    # All should have NOT_STARTED status
    for mod in modules:
        assert mod.status == ModuleStatus.NOT_STARTED
        assert mod.carbon_report_id == inv.id


@pytest.mark.asyncio
async def test_service_list_inventories_by_unit(async_session):
    service = CarbonReportService(async_session)
    await service.create(CarbonReportCreate(year=2025, unit_id=1))
    await service.create(CarbonReportCreate(year=2026, unit_id=1))
    await service.create(CarbonReportCreate(year=2025, unit_id=2))
    items = await service.list_by_unit(1)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_service_update_and_delete(async_session):
    service = CarbonReportService(async_session)
    data = CarbonReportCreate(year=2025, unit_id=1)
    inv = await service.create(data)

    update = CarbonReportUpdate(year=2026, unit_id=1)
    updated = await service.update(inv.id, update)
    assert updated.year == 2026

    # Delete should also delete associated modules
    deleted = await service.delete(inv.id)
    assert deleted is True
    assert await service.get(inv.id) is None

    # Modules should also be deleted
    modules = await service.module_service.list_modules(inv.id)
    assert len(modules) == 0


@pytest.mark.asyncio
async def test_module_status_update(async_session):
    """Test updating module status via service."""
    service = CarbonReportService(async_session)
    inv = await service.create(CarbonReportCreate(year=2025, unit_id=1))

    # Update a module status
    module_type_id = 1  # my-lab
    updated = await service.module_service.update_status(
        inv.id, module_type_id, ModuleStatus.IN_PROGRESS
    )
    assert updated is not None
    assert updated.status == ModuleStatus.IN_PROGRESS

    # Verify it persists
    modules = await service.module_service.list_modules(inv.id)
    my_lab_mod = next(m for m in modules if m.module_type_id == module_type_id)
    assert my_lab_mod.status == ModuleStatus.IN_PROGRESS
