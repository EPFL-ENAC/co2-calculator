"""Factor service with document

Manages factor lifecycle with full audit trail.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry_type import DataEntryTypeEnum
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

    def __init__(
        self,
        repo: Optional[FactorRepository] = None,
    ):
        self.repo = repo or FactorRepository()

    async def get(self, session: AsyncSession, factor_id: int) -> Optional[Factor]:
        """Get factor by ID."""
        return await self.repo.get(session, factor_id)

    async def get_power_factor(
        self,
        session: AsyncSession,
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
        session: AsyncSession,
        data_entry_type_id: DataEntryTypeEnum,
        emission_type_id: EmissionTypeEnum,
    ) -> Optional[Factor]:
        """Get headcount factor for variant (student/member)."""
        return await self.repo.get_current_factor(
            session,
            emission_type_id=emission_type_id,
            data_entry_type_id=data_entry_type_id,
        )

    async def list_by_family(
        self,
        session: AsyncSession,
        data_entry_type_id: DataEntryTypeEnum,
        include_expired: bool = False,
    ) -> List[Factor]:
        """List all factors for a family."""
        return await self.repo.list_by_data_entry_type(
            session, data_entry_type_id, include_expired
        )

    async def get_class_subclass_map(
        self, session: AsyncSession, variant_type_id: int
    ) -> Dict[str, List[str]]:
        """Get class/subclass mapping for power factors."""
        raise NotImplementedError
        # return await self.repo.get_class_subclass_map(session, variant_type_id)

    async def create_factor(
        self,
        session: AsyncSession,
        factor_family: str,
        values: Dict[str, Any],
        created_by: str,
        variant_type_id: Optional[int] = None,
        classification: Optional[Dict] = None,
        value_units: Optional[Dict] = None,
        source: Optional[str] = None,
        meta: Optional[Dict] = None,
        change_reason: Optional[str] = None,
    ) -> Factor:
        """
        Create a new factor with document versioning.

        Args:
            session: Database session
            factor_family: Factor family (e.g., 'power', 'headcount')
            values: Factor values dict
            created_by: User creating the factor
            variant_type_id: Optional variant type scope
            classification: Optional classification dict
            value_units: Optional units dict for each value
            source: Optional data source
            meta: Optional additional metadata
            change_reason: Optional reason for creation

        Returns:
            The created Factor
        """
        now = datetime.now(timezone.utc)

        factor = Factor(
            factor_family=factor_family,
            variant_type_id=variant_type_id,
            classification=classification or {},
            values=values,
            value_units=value_units,
            valid_from=now,
            source=source,
            meta=meta or {},
            created_at=now,
            created_by=created_by,
        )

        factor = await self.repo.create(session, factor)

        logger.info(f"Created factor {factor.id} ({factor_family}) by {created_by}")
        return factor

    async def update_factor(
        self,
        session: AsyncSession,
        factor_id: int,
        updated_by: str,
        values: Optional[Dict[str, Any]] = None,
        classification: Optional[Dict] = None,
        source: Optional[str] = None,
        meta: Optional[Dict] = None,
        change_reason: Optional[str] = None,
    ) -> Optional[Factor]:
        """
        Update a factor with document.

        Creates a new version of the factor and expires the old one.
        This triggers batch recalculation for affected emissions.

        Args:
            session: Database session
            factor_id: ID of factor to update
            updated_by: User making the update
            values: New values dict (if changing)
            classification: New classification (if changing)
            value_units: New units dict (if changing)
            source: New source (if changing)
            meta: New metadata (if changing)
            change_reason: Reason for the change

        Returns:
            The new factor version, or None if original not found
        """
        old_factor = await self.repo.get(session, factor_id)
        if not old_factor:
            logger.warning(f"Factor {factor_id} not found for update")
            return None

        now = datetime.now(timezone.utc)

        # Expire old factor
        old_factor.valid_to = now
        session.add(old_factor)

        # Create new version
        new_factor = Factor(
            emission_type_id=old_factor.emission_type_id,
            data_entry_type_id=old_factor.data_entry_type_id,
            classification=classification
            if classification is not None
            else old_factor.classification,
            values=values if values is not None else old_factor.values,
            valid_from=now,
            created_at=now,
            created_by=updated_by,
        )

        new_factor = await self.repo.create(session, new_factor)

        return new_factor

    async def find_modules_for_recalculation(
        self, session: AsyncSession, factor_id: int
    ) -> List[int]:
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
