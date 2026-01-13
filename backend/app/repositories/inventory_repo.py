"""Inventory repository for database operations."""

from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryCreate, InventoryUpdate

logger = get_logger(__name__)


class InventoryRepository:
    """Repository for Inventory database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_inventory(self, data: InventoryCreate) -> Inventory:
        db_obj = Inventory.model_validate(data.dict())
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def get_inventory(self, inventory_id: int) -> Optional[Inventory]:
        statement = select(Inventory).where(Inventory.id == inventory_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_inventories_by_unit(self, unit_id: int) -> list[Inventory]:
        statement = select(Inventory).where(Inventory.unit_id == unit_id)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_inventory_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> Optional[Inventory]:
        statement = select(Inventory).where(
            (Inventory.unit_id == unit_id) & (Inventory.year == year)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update_inventory(
        self, inventory_id: int, data: InventoryUpdate
    ) -> Optional[Inventory]:
        statement = select(Inventory).where(Inventory.id == inventory_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete_inventory(self, inventory_id: int) -> bool:
        statement = select(Inventory).where(Inventory.id == inventory_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.commit()
        return True
