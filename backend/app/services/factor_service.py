"""Factor service with document

Manages factor lifecycle with full audit trail.
"""

from typing import Any, Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository

logger = get_logger(__name__)


class FactorService:
    """
    Service for managing factors

    Features:
    - CRUD operations on factors
    - Automatic document for all changes
    - Factor expiration (not deletion)
    - Lookup methods for power/headcount factors
    """

    ENTITY_TYPE = "factors"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorRepository(session)

    async def get(self, id: int) -> Optional[Factor]:
        """Get factor by ID."""
        return await self.repo.get(id)

    async def get_power_factor(
        self,
        variant_type_id: int,
        equipment_class: str,
        sub_class: Optional[str] = None,
    ) -> Optional[Factor]:
        """Get power factor for equipment classification."""
        # TODO: implement
        raise NotImplementedError
        # return await self.repo.get(session, variant_type_id,
        # equipment_class, sub_class)

    async def get_headcount_factor(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        emission_type_id: EmissionTypeEnum,
    ) -> Optional[Factor]:
        """Get headcount factor for variant (student/member)."""
        return await self.repo.get_current_factor(
            emission_type_id=emission_type_id,
            data_entry_type_id=data_entry_type_id,
        )

    async def list_id_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
    ) -> List[int]:
        """List all factors for a data entry type and emission type."""
        return await self.repo.list_id_by_data_entry_type(data_entry_type_id)

    async def list_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
    ) -> List[Factor]:
        """List all factors for a data entry type and emission type."""
        return await self.repo.list_by_data_entry_type(data_entry_type_id)

    async def get_class_subclass_map(
        self, session: AsyncSession, variant_type_id: int
    ) -> Dict[str, List[str]]:
        """Get class/subclass mapping for power factors."""
        raise NotImplementedError
        # return await self.repo.get_class_subclass_map(session, variant_type_id)

    async def prepare_create(
        self,
        emission_type_id: EmissionTypeEnum,
        is_conversion: bool,
        data_entry_type_id: DataEntryTypeEnum,
        classification: Dict[str, Any],
        values: Dict[str, float],
    ) -> Factor:
        """Prepare a factor for creation."""

        factor = Factor(
            emission_type_id=emission_type_id,
            is_conversion=is_conversion,
            data_entry_type_id=data_entry_type_id,
            classification=classification,
            values=values,
        )

        return factor

    async def create(
        self,
        session: AsyncSession,
        factor: Factor,
    ) -> Factor:
        factor = await self.prepare_create(
            factor.emission_type_id,
            factor.is_conversion,
            factor.data_entry_type_id,
            factor.classification,
            factor.values,
        )

        factor = await self.repo.create(session, factor)

        return factor

    async def update(
        self,
        session: AsyncSession,
        factor_id: int,
        new_factor: Factor,
    ) -> Optional[Factor]:
        """Update an existing factor."""
        raise NotImplementedError

    async def bulk_create(self, factors: List[Factor]) -> List[Factor]:
        """Bulk create factors."""
        return await self.repo.bulk_create(factors)

    async def bulk_delete(self, factor_ids: list[int]) -> None:
        """Bulk delete factors by family."""
        return await self.repo.bulk_delete(factor_ids)

    async def bulk_delete_by_data_entry_type(
        self, data_entry_type_id: DataEntryTypeEnum
    ) -> None:
        """Bulk delete factors by data entry type."""
        factor_ids = await self.repo.list_id_by_data_entry_type(
            data_entry_type_id=data_entry_type_id,
        )
        await self.repo.bulk_delete(factor_ids)

    async def find_modules_for_recalculation(self, factor_id: int) -> List[int]:
        """Find module IDs that need recalculation when factor changes."""
        raise NotImplementedError
        # return await self.repo.find_modules_for_recalculation(session, factor_id)


# Singleton instance
_factor_service: Optional[FactorService] = None


def get_factor_service() -> FactorService:
    """Get or create the factor service singleton."""
    global _factor_service
    if _factor_service is None:
        _factor_service = FactorService()
    return _factor_service
