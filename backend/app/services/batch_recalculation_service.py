"""Batch recalculation service for handling factor changes.

Coordinates recalculation of emissions when factors are updated.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.factor import Factor
from app.models.module import Module
from app.models.module_emission import ModuleEmission
from app.services.emission_calculation_service import (
    EmissionCalculationService,
    get_emission_calculation_service,
)
from app.services.factor_service import FactorService, get_factor_service

logger = get_logger(__name__)


class RecalculationStatus(str, Enum):
    """Status of a recalculation job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some succeeded, some failed


@dataclass
class RecalculationResult:
    """Result of a batch recalculation."""

    status: RecalculationStatus
    factor_id: int
    total_modules: int
    successful: int
    failed: int
    started_at: datetime
    completed_at: Optional[datetime]
    failed_module_ids: List[int]
    error_messages: List[str]


class BatchRecalculationService:
    """
    Service for batch recalculation of emissions when factors change.

    This service:
    - Finds all modules affected by a factor change
    - Marks existing emissions as non-current
    - Recalculates emissions with new factor values
    - Tracks success/failure for each module
    """

    def __init__(
        self,
        factor_service: Optional[FactorService] = None,
        emission_service: Optional[EmissionCalculationService] = None,
    ):
        self.factor_service = factor_service or get_factor_service()
        self.emission_service = emission_service or get_emission_calculation_service()

    async def find_affected_modules(
        self, session: AsyncSession, factor_id: int
    ) -> List[int]:
        """
        Find all module IDs that have emissions using the given factor.

        Returns list of unique module IDs that need recalculation.

        Note: Uses primary_factor_id FK on module_emissions (no join table).
        """
        stmt = (
            select(ModuleEmission.module_id)
            .where(
                ModuleEmission.primary_factor_id == factor_id,
                ModuleEmission.is_current == True,  # noqa: E712
            )
            .distinct()
        )

        result = await session.exec(stmt)
        return list(result.all())

    async def find_affected_modules_by_family(
        self,
        session: AsyncSession,
        factor_family: str,
        variant_type_id: Optional[int] = None,
    ) -> List[int]:
        """
        Find all modules affected by any factor in a family.

        Useful for bulk recalculation when multiple factors change.

        Note: Uses primary_factor_id FK on module_emissions (no join table).
        """
        # Get all current factors in the family
        stmt = select(Factor.id).where(
            col(Factor.factor_family) == factor_family,
            col(Factor.valid_to).is_(None),
        )
        if variant_type_id is not None:
            stmt = stmt.where(col(Factor.variant_type_id) == variant_type_id)

        result = await session.exec(stmt)
        factor_ids = list(result.all())

        if not factor_ids:
            return []

        # Find all modules using these factors (direct FK query)
        stmt = (
            select(ModuleEmission.module_id)
            .where(
                ModuleEmission.primary_factor_id.in_(factor_ids),
                ModuleEmission.is_current == True,  # noqa: E712
            )
            .distinct()
        )

        result = await session.exec(stmt)
        return list(result.all())

    async def recalculate_for_factor(
        self,
        session: AsyncSession,
        factor_id: int,
        emission_factor_value: Optional[float] = None,
        emission_factor_id: Optional[int] = None,
    ) -> RecalculationResult:
        """
        Recalculate all emissions affected by a factor change.

        This is the main entry point for batch recalculation.

        Args:
            session: Database session
            factor_id: The changed factor ID
            emission_factor_value: Optional emission factor to use
            emission_factor_id: Optional emission factor ID

        Returns:
            RecalculationResult with statistics
        """
        started_at = datetime.now(timezone.utc)
        module_ids = await self.find_affected_modules(session, factor_id)

        logger.info(
            f"Starting batch recalculation for factor {factor_id}: "
            f"{len(module_ids)} modules affected"
        )

        if not module_ids:
            return RecalculationResult(
                status=RecalculationStatus.COMPLETED,
                factor_id=factor_id,
                total_modules=0,
                successful=0,
                failed=0,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                failed_module_ids=[],
                error_messages=[],
            )

        successful = 0
        failed = 0
        failed_module_ids: List[int] = []
        error_messages: List[str] = []

        # Process each module
        for module_id in module_ids:
            try:
                # Get the module
                stmt = select(Module).where(col(Module.id) == module_id)
                result = await session.exec(stmt)
                module = result.one_or_none()

                if not module:
                    logger.warning(f"Module {module_id} not found, skipping")
                    failed += 1
                    failed_module_ids.append(module_id)
                    error_messages.append(f"Module {module_id} not found")
                    continue

                # Recalculate emissions
                await self.emission_service.calculate_for_module(
                    session=session,
                    module=module,
                    emission_factor_value=emission_factor_value,
                    emission_factor_id=emission_factor_id,
                    persist=True,
                )

                successful += 1
                logger.debug(f"Recalculated emissions for module {module_id}")

            except Exception as e:
                logger.error(f"Failed to recalculate module {module_id}: {e}")
                failed += 1
                failed_module_ids.append(module_id)
                error_messages.append(f"Module {module_id}: {str(e)}")

        # Commit all changes
        await session.commit()

        completed_at = datetime.now(timezone.utc)

        # Determine final status
        if failed == 0:
            status = RecalculationStatus.COMPLETED
        elif successful == 0:
            status = RecalculationStatus.FAILED
        else:
            status = RecalculationStatus.PARTIAL

        result = RecalculationResult(
            status=status,
            factor_id=factor_id,
            total_modules=len(module_ids),
            successful=successful,
            failed=failed,
            started_at=started_at,
            completed_at=completed_at,
            failed_module_ids=failed_module_ids,
            error_messages=error_messages,
        )

        logger.info(
            f"Batch recalculation for factor {factor_id} completed: "
            f"{successful}/{len(module_ids)} successful, {failed} failed"
        )

        return result

    async def recalculate_for_modules(
        self,
        session: AsyncSession,
        module_ids: List[int],
        emission_factor_value: Optional[float] = None,
        emission_factor_id: Optional[int] = None,
    ) -> RecalculationResult:
        """
        Recalculate emissions for a specific list of modules.

        Useful for manual recalculation or selective updates.
        """
        started_at = datetime.now(timezone.utc)

        logger.info(f"Starting recalculation for {len(module_ids)} modules")

        if not module_ids:
            return RecalculationResult(
                status=RecalculationStatus.COMPLETED,
                factor_id=0,
                total_modules=0,
                successful=0,
                failed=0,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                failed_module_ids=[],
                error_messages=[],
            )

        successful = 0
        failed = 0
        failed_module_ids: List[int] = []
        error_messages: List[str] = []

        for module_id in module_ids:
            try:
                stmt = select(Module).where(col(Module.id) == module_id)
                result = await session.exec(stmt)
                module = result.one_or_none()

                if not module:
                    failed += 1
                    failed_module_ids.append(module_id)
                    error_messages.append(f"Module {module_id} not found")
                    continue

                await self.emission_service.calculate_for_module(
                    session=session,
                    module=module,
                    emission_factor_value=emission_factor_value,
                    emission_factor_id=emission_factor_id,
                    persist=True,
                )

                successful += 1

            except Exception as e:
                logger.error(f"Failed to recalculate module {module_id}: {e}")
                failed += 1
                failed_module_ids.append(module_id)
                error_messages.append(f"Module {module_id}: {str(e)}")

        await session.commit()

        if failed == 0:
            status = RecalculationStatus.COMPLETED
        elif successful == 0:
            status = RecalculationStatus.FAILED
        else:
            status = RecalculationStatus.PARTIAL

        return RecalculationResult(
            status=status,
            factor_id=0,
            total_modules=len(module_ids),
            successful=successful,
            failed=failed,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            failed_module_ids=failed_module_ids,
            error_messages=error_messages,
        )

    async def mark_emissions_stale(self, session: AsyncSession, factor_id: int) -> int:
        """
        Mark all emissions using a factor as not current.

        This is useful when a factor is invalidated and emissions
        should be flagged for recalculation without immediate processing.

        Returns the number of emissions marked stale.

        Note: Uses primary_factor_id FK on module_emissions (no join table).
        """
        from sqlmodel import update

        # Direct query - no join needed
        update_stmt = (
            update(ModuleEmission)
            .where(
                ModuleEmission.primary_factor_id == factor_id,
                ModuleEmission.is_current == True,  # noqa: E712
            )
            .values(is_current=False)
        )

        result = await session.exec(update_stmt)  # type: ignore
        await session.commit()

        count = result.rowcount if result else 0
        logger.info(f"Marked {count} emissions as stale for factor {factor_id}")

        return count


# Singleton instance
_batch_service: Optional[BatchRecalculationService] = None


def get_batch_recalculation_service() -> BatchRecalculationService:
    """Get or create the batch recalculation service singleton."""
    global _batch_service
    if _batch_service is None:
        _batch_service = BatchRecalculationService()
    return _batch_service
