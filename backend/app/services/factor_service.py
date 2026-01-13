"""Factor service with document versioning and change tracking.

Manages factor lifecycle with full audit trail.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository
from app.services.document_versioning_service import (
    DocumentVersioningService,
    get_document_versioning_service,
)

logger = get_logger(__name__)


class FactorService:
    """
    Service for managing factors with versioning and audit trail.

    Features:
    - CRUD operations on factors
    - Automatic document versioning for all changes
    - Factor expiration (not deletion)
    - Lookup methods for power/headcount factors
    """

    ENTITY_TYPE = "factors"

    def __init__(
        self,
        repo: Optional[FactorRepository] = None,
        versioning_service: Optional[DocumentVersioningService] = None,
    ):
        self.repo = repo or FactorRepository()
        self.versioning = versioning_service or get_document_versioning_service()

    def _factor_to_snapshot(self, factor: Factor) -> Dict[str, Any]:
        """Convert factor to snapshot dict for versioning."""
        return {
            "id": factor.id,
            "emission_type_id": factor.emission_type_id,
            "is_conversion": factor.is_conversion,
            "data_entry_type_id": factor.data_entry_type_id,
            "classification": factor.classification,
            "values": factor.values,
        }

    async def get_by_id(
        self, session: AsyncSession, factor_id: int
    ) -> Optional[Factor]:
        """Get factor by ID."""
        return await self.repo.get_by_id(session, factor_id)

    async def get_power_factor(
        self,
        session: AsyncSession,
        variant_type_id: int,
        equipment_class: str,
        sub_class: Optional[str] = None,
    ) -> Optional[Factor]:
        """Get power factor for equipment classification."""
        return await self.repo.get_power_factor(
            session, variant_type_id, equipment_class, sub_class
        )

    async def get_headcount_factor(
        self, session: AsyncSession, variant_type_id: int
    ) -> Optional[Factor]:
        """Get headcount factor for variant (student/member)."""
        return await self.repo.get_current_factor(
            session, factor_family="headcount", variant_type_id=variant_type_id
        )

    async def list_by_family(
        self,
        session: AsyncSession,
        factor_family: str,
        include_expired: bool = False,
    ) -> List[Factor]:
        """List all factors for a family."""
        return await self.repo.list_by_family(session, factor_family, include_expired)

    async def get_class_subclass_map(
        self, session: AsyncSession, variant_type_id: int
    ) -> Dict[str, List[str]]:
        """Get class/subclass mapping for power factors."""
        return await self.repo.get_class_subclass_map(session, variant_type_id)

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
            version=1,
            valid_from=now,
            valid_to=None,
            source=source,
            meta=meta or {},
            created_at=now,
            created_by=created_by,
        )

        factor = await self.repo.create(session, factor)

        # Create document version
        await self.versioning.create_version(
            session=session,
            entity_type=self.ENTITY_TYPE,
            entity_id=factor.id,
            data_snapshot=self._factor_to_snapshot(factor),
            change_type="CREATE",
            changed_by=created_by,
            change_reason=change_reason or "Initial creation",
        )

        logger.info(f"Created factor {factor.id} ({factor_family}) by {created_by}")
        return factor

    async def update_factor(
        self,
        session: AsyncSession,
        factor_id: int,
        updated_by: str,
        values: Optional[Dict[str, Any]] = None,
        classification: Optional[Dict] = None,
        value_units: Optional[Dict] = None,
        source: Optional[str] = None,
        meta: Optional[Dict] = None,
        change_reason: Optional[str] = None,
    ) -> Optional[Factor]:
        """
        Update a factor with document versioning.

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
        old_factor = await self.repo.get_by_id(session, factor_id)
        if not old_factor:
            logger.warning(f"Factor {factor_id} not found for update")
            return None

        now = datetime.now(timezone.utc)

        # Expire old factor
        old_factor.valid_to = now
        session.add(old_factor)

        # Create new version
        new_factor = Factor(
            factor_family=old_factor.factor_family,
            variant_type_id=old_factor.variant_type_id,
            classification=classification
            if classification is not None
            else old_factor.classification,
            values=values if values is not None else old_factor.values,
            value_units=value_units
            if value_units is not None
            else old_factor.value_units,
            version=old_factor.version + 1,
            valid_from=now,
            valid_to=None,
            source=source if source is not None else old_factor.source,
            meta=meta if meta is not None else old_factor.meta,
            created_at=now,
            created_by=updated_by,
        )

        new_factor = await self.repo.create(session, new_factor)

        # Create document version
        await self.versioning.create_version(
            session=session,
            entity_type=self.ENTITY_TYPE,
            entity_id=new_factor.id,
            data_snapshot=self._factor_to_snapshot(new_factor),
            change_type="UPDATE",
            changed_by=updated_by,
            change_reason=change_reason,
        )

        logger.info(
            f"Updated factor {factor_id} → {new_factor.id} "
            f"(v{old_factor.version} → v{new_factor.version}) by {updated_by}"
        )

        return new_factor

    async def expire_factor(
        self,
        session: AsyncSession,
        factor_id: int,
        expired_by: str,
        change_reason: Optional[str] = None,
    ) -> Optional[Factor]:
        """
        Expire (soft-delete) a factor.

        Args:
            session: Database session
            factor_id: ID of factor to expire
            expired_by: User expiring the factor
            change_reason: Reason for expiration

        Returns:
            The expired factor, or None if not found
        """
        factor = await self.repo.expire_factor(session, factor_id)
        if not factor:
            return None

        # Create document version for deletion
        await self.versioning.create_version(
            session=session,
            entity_type=self.ENTITY_TYPE,
            entity_id=factor.id,
            data_snapshot=self._factor_to_snapshot(factor),
            change_type="DELETE",
            changed_by=expired_by,
            change_reason=change_reason or "Factor expired",
        )

        logger.info(f"Expired factor {factor_id} by {expired_by}")
        return factor

    async def get_version_history(
        self, session: AsyncSession, factor_id: int
    ) -> List[Dict]:
        """Get version history for a factor."""
        versions = await self.versioning.list_versions(
            session, self.ENTITY_TYPE, factor_id
        )
        return [
            {
                "version": v.version,
                "change_type": v.change_type,
                "change_reason": v.change_reason,
                "changed_by": v.changed_by,
                "changed_at": v.changed_at,
                "data_diff": v.data_diff,
            }
            for v in versions
        ]

    async def rollback_factor(
        self,
        session: AsyncSession,
        factor_id: int,
        target_version: int,
        rolled_back_by: str,
        change_reason: Optional[str] = None,
    ) -> Optional[Factor]:
        """
        Rollback a factor to a previous version.

        This creates a new factor with the old data, not a mutation.

        Args:
            session: Database session
            factor_id: Current factor ID
            target_version: Version number to rollback to
            rolled_back_by: User performing rollback
            change_reason: Reason for rollback

        Returns:
            The new factor with rolled-back data, or None if failed
        """
        # Get target version data
        target = await self.versioning.get_version(
            session, self.ENTITY_TYPE, factor_id, target_version
        )
        if not target:
            logger.warning(f"Target version {target_version} not found for rollback")
            return None

        old_data = target.data_snapshot

        # Expire current factor
        current = await self.repo.get_by_id(session, factor_id)
        if current and current.valid_to is None:
            current.valid_to = datetime.now(timezone.utc)
            session.add(current)

        # Create new factor from old data
        now = datetime.now(timezone.utc)
        new_factor = Factor(
            factor_family=old_data.get("factor_family"),
            variant_type_id=old_data.get("variant_type_id"),
            classification=old_data.get("classification", {}),
            values=old_data.get("values", {}),
            value_units=old_data.get("value_units"),
            version=(current.version + 1) if current else 1,
            valid_from=now,
            valid_to=None,
            source=old_data.get("source"),
            metadata=old_data.get("metadata", {}),
            created_at=now,
            created_by=rolled_back_by,
        )

        new_factor = await self.repo.create(session, new_factor)

        # Create rollback document version
        await self.versioning.create_version(
            session=session,
            entity_type=self.ENTITY_TYPE,
            entity_id=new_factor.id,
            data_snapshot=self._factor_to_snapshot(new_factor),
            change_type="ROLLBACK",
            changed_by=rolled_back_by,
            change_reason=change_reason or f"Rollback to version {target_version}",
        )

        logger.info(
            f"Rolled back factor {factor_id} to version {target_version} "
            f"→ new factor {new_factor.id} by {rolled_back_by}"
        )

        return new_factor

    async def find_modules_for_recalculation(
        self, session: AsyncSession, factor_id: int
    ) -> List[int]:
        """Find module IDs that need recalculation when factor changes."""
        return await self.repo.find_modules_for_recalculation(session, factor_id)


# Singleton instance
_factor_service: Optional[FactorService] = None


def get_factor_service() -> FactorService:
    """Get or create the factor service singleton."""
    global _factor_service
    if _factor_service is None:
        _factor_service = FactorService()
    return _factor_service
