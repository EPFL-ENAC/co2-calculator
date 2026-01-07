"""InventoryModule repository for database operations."""

from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.core.logging import get_logger
from app.models.inventory import InventoryModule

logger = get_logger(__name__)


class InventoryModuleRepository:
    """Repository for InventoryModule database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        inventory_id: int,
        module_type_id: int,
        status: int = ModuleStatus.NOT_STARTED,
    ) -> InventoryModule:
        """Create a new inventory module record."""
        db_obj = InventoryModule(
            inventory_id=inventory_id,
            module_type_id=module_type_id,
            status=status,
        )
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def create_bulk(
        self,
        inventory_id: int,
        module_type_ids: List[int],
        status: int = ModuleStatus.NOT_STARTED,
    ) -> List[InventoryModule]:
        """Create multiple inventory module records in one transaction."""
        db_objects = [
            InventoryModule(
                inventory_id=inventory_id,
                module_type_id=module_type_id,
                status=status,
            )
            for module_type_id in module_type_ids
        ]
        self.session.add_all(db_objects)
        await self.session.commit()
        for obj in db_objects:
            await self.session.refresh(obj)
        return db_objects

    async def get(self, inventory_module_id: int) -> Optional[InventoryModule]:
        """Get an inventory module by ID."""
        statement = select(InventoryModule).where(
            InventoryModule.id == inventory_module_id
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_inventory_and_module_type(
        self, inventory_id: int, module_type_id: int
    ) -> Optional[InventoryModule]:
        """Get an inventory module by inventory ID and module type ID."""
        statement = select(InventoryModule).where(
            InventoryModule.inventory_id == inventory_id,
            InventoryModule.module_type_id == module_type_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_inventory(self, inventory_id: int) -> List[InventoryModule]:
        """List all inventory modules for a given inventory."""
        statement = (
            select(InventoryModule)
            .where(InventoryModule.inventory_id == inventory_id)
            .order_by("module_type_id")
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_status(
        self, inventory_id: int, module_type_id: int, status: int
    ) -> Optional[InventoryModule]:
        """Update the status of an inventory module."""
        statement = select(InventoryModule).where(
            InventoryModule.inventory_id == inventory_id,
            InventoryModule.module_type_id == module_type_id,
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None
        db_obj.status = status
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, inventory_module_id: int) -> bool:
        """Delete an inventory module by ID."""
        statement = select(InventoryModule).where(
            InventoryModule.id == inventory_module_id
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.commit()
        return True

    async def delete_by_inventory(self, inventory_id: int) -> int:
        """Delete all inventory modules for a given inventory. Returns count deleted."""
        statement = select(InventoryModule).where(
            InventoryModule.inventory_id == inventory_id
        )
        result = await self.session.execute(statement)
        db_objects = list(result.scalars().all())
        count = len(db_objects)
        for obj in db_objects:
            await self.session.delete(obj)
        await self.session.commit()
        return count
