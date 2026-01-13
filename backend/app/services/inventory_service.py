"""Inventory service for business logic."""

from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.inventory import Inventory
from app.repositories.inventory_repo import InventoryRepository
from app.schemas.inventory import InventoryCreate, InventoryUpdate
from app.services.inventory_module_service import InventoryModuleService

logger = get_logger(__name__)


class InventoryService:
    """Service for inventory business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryRepository(session)
        self.module_service = InventoryModuleService(session)

    async def create_inventory(self, data: InventoryCreate) -> Inventory:
        """
        Create a new inventory and auto-create all module records.

        After creating the inventory, this automatically creates one
        InventoryModule per module type (7 total) with status NOT_STARTED.
        """
        inventory = await self.repo.create_inventory(data)
        logger.info(
            f"Created inventory {sanitize(inventory.id)} for unit "
            f"{sanitize(data.unit_id)} year {sanitize(data.year)}"
        )

        # Auto-create all inventory modules with default status
        assert inventory.id is not None
        await self.module_service.create_all_modules_for_inventory(inventory.id)

        return inventory

    async def get_inventory(self, inventory_id: int) -> Optional[Inventory]:
        return await self.repo.get_inventory(inventory_id)

    async def list_inventories_by_unit(self, unit_id: int) -> List[Inventory]:
        return await self.repo.list_inventories_by_unit(unit_id)

    async def get_inventory_by_unit_and_year(
        self, unit_id: int, year: int
    ) -> Optional[Inventory]:
        return await self.repo.get_inventory_by_unit_and_year(unit_id, year)

    async def update_inventory(
        self, inventory_id: int, data: InventoryUpdate
    ) -> Optional[Inventory]:
        return await self.repo.update_inventory(inventory_id, data)

    async def delete_inventory(self, inventory_id: int) -> bool:
        """
        Delete an inventory and all its associated modules.
        """
        # First delete all associated modules
        await self.module_service.delete_all_modules_for_inventory(inventory_id)
        # Then delete the inventory
        return await self.repo.delete_inventory(inventory_id)
