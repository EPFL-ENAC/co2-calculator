"""InventoryModule service for business logic."""

from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ALL_MODULE_TYPE_IDS, ModuleStatus
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.inventory import InventoryModule
from app.repositories.inventory_module_repo import InventoryModuleRepository

logger = get_logger(__name__)


class InventoryModuleService:
    """Service for inventory module business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryModuleRepository(session)

    async def create_all_modules_for_inventory(
        self, inventory_id: int
    ) -> List[InventoryModule]:
        """
        Create all module records for a new inventory.

        Creates one InventoryModule per module type (7 total) with status NOT_STARTED.
        This is called automatically when a new inventory is created.
        """
        module_type_ids = [int(mt) for mt in ALL_MODULE_TYPE_IDS]
        logger.info(
            f"Creating {sanitize(len(module_type_ids))} inventory modules "
            f"for inventory {sanitize(inventory_id)}"
        )
        return await self.repo.create_bulk(
            inventory_id=inventory_id,
            module_type_ids=module_type_ids,
            status=ModuleStatus.NOT_STARTED,
        )

    async def get_module(
        self, inventory_id: int, module_type_id: int
    ) -> Optional[InventoryModule]:
        """Get an inventory module by inventory and module type."""
        return await self.repo.get_by_inventory_and_module_type(
            inventory_id, module_type_id
        )

    async def list_modules(self, inventory_id: int) -> List[InventoryModule]:
        """List all modules for an inventory."""
        return await self.repo.list_by_inventory(inventory_id)

    async def update_status(
        self, inventory_id: int, module_type_id: int, status: int
    ) -> Optional[InventoryModule]:
        """
        Update the status of an inventory module.

        Args:
            inventory_id: The inventory ID
            module_type_id: The module type ID (1-7)
            status: The new status (0=not_started, 1=in_progress, 2=validated)

        Returns:
            The updated InventoryModule or None if not found
        """
        # Validate status value
        if status not in [s.value for s in ModuleStatus]:
            raise ValueError(
                f"Invalid status {status}. Must be one of: "
                f"{[s.value for s in ModuleStatus]}"
            )

        logger.info(
            f"Updt inventory {sanitize(inventory_id)} module {sanitize(module_type_id)}"
            f"status to {sanitize(ModuleStatus(status).name)}"
        )
        return await self.repo.update_status(inventory_id, module_type_id, status)

    async def delete_all_modules_for_inventory(self, inventory_id: int) -> int:
        """Delete all modules for an inventory. Returns count deleted."""
        return await self.repo.delete_by_inventory(inventory_id)
