"""Factor service with document

Manages factor lifecycle with full audit trail.
"""

from typing import Any, Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
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

    async def get_by_classification(
        self,
        data_entry_type: DataEntryTypeEnum,
        kind: str,
        subkind: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Optional[Factor]:
        """Get power factor for given equipment class and optional subclass.

        Args:
            data_entry_type: Data entry type filter
            kind: Primary classification key
            subkind: Secondary classification key (optional)
            year: Year filter for year-scoped factors (should be provided)
        """
        return await self.repo.get_by_classification(
            data_entry_type=data_entry_type,
            kind=kind,
            subkind=subkind,
            year=year,
        )

    async def get_factors(
        self,
        data_entry_type: DataEntryTypeEnum,
        fallbacks: Optional[Dict[str, Any]] = None,
        year: Optional[int] = None,
        **classification: Any,
    ) -> List[Factor]:
        """Flexible factor lookup with dynamic classification filters and fallbacks.

        Forwards to ``FactorRepository.get_factors``.

        Args:
            data_entry_type: Scopes the query to this data entry type.
            fallbacks: Optional fallback values for classification keys
                       (e.g. ``{"country_code": "RoW"}``).
            year: Year filter for year-scoped factors (should be provided)
            **classification: Arbitrary classification key/value filters
                              (e.g. ``kind="plane"``, ``category="short_haul"``).

        Returns:
            List of matching factors.
        """
        return await self.repo.get_factors(
            data_entry_type=data_entry_type,
            fallbacks=fallbacks,
            year=year,
            **classification,
        )

    async def list_id_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: Optional[int] = None,
    ) -> List[int]:
        """List all factors for a data entry type and emission type.

        Args:
            data_entry_type_id: Data entry type filter
            year: Optional year filter for year-scoped factors
        """
        return await self.repo.list_id_by_data_entry_type(data_entry_type_id, year)

    async def count_by_data_entry_type_and_year(
        self,
        data_entry_type_id: int,
        year: int,
    ) -> int:
        """Count factors for data entry type and specific year.

        Args:
            data_entry_type_id: Data entry type ID (int value)
            year: Year filter (mandatory)
        """
        return await self.repo.count_by_data_entry_type_and_year(
            data_entry_type_id=data_entry_type_id,
            year=year,
        )

    async def list_by_emission_type(
        self,
        emission_type: EmissionType,
        year: Optional[int] = None,
    ) -> List[Factor]:
        """List all factors for a given emission type.

        Args:
            emission_type: Emission type filter
            year: Optional year filter for year-scoped factors
        """
        return await self.repo.list_by_emission_type(emission_type, year)

    async def list_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: Optional[int] = None,
    ) -> List[Factor]:
        """List all factors for a data entry type and emission type.

        Args:
            data_entry_type_id: Data entry type filter
            year: Optional year filter for year-scoped factors
        """
        return await self.repo.list_by_data_entry_type(data_entry_type_id, year)

    async def get_class_subclass_map(
        self,
        data_entry_type: DataEntryTypeEnum,
        kind_field: str,
        subkind_field: str,
    ) -> Dict[str, List[str]]:
        """Get class/subclass mapping for power factors."""
        return await self.repo.get_class_subclass_map(
            data_entry_type=data_entry_type,
            kind_field=kind_field,
            subkind_field=subkind_field,
        )

    async def prepare_create(
        self,
        emission_type_id: int,  # DataEntryTypeEnum, #
        data_entry_type_id: int,  # DataEntryTypeEnum,
        classification: Dict[str, Any],
        values: Dict[str, float | int | str | None],
        year: Optional[int] = None,
    ) -> Factor:
        """Prepare a factor for creation.

        Args:
            emission_type_id: Emission type ID
            data_entry_type_id: Data entry type ID
            classification: Classification dictionary
            values: Factor values dictionary
            year: Year for which this factor applies
        """

        factor = Factor(
            emission_type_id=emission_type_id,
            data_entry_type_id=data_entry_type_id,
            classification=classification,
            values=values,
            year=year,
        )
        return factor

    async def create(
        self,
        session: AsyncSession,
        factor: Factor,
    ) -> Factor:
        factor = await self.prepare_create(
            factor.emission_type_id,
            factor.data_entry_type_id,
            factor.classification,
            factor.values,
            factor.year,
        )

        factor = await self.repo.create(factor)

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
        self,
        data_entry_type_id: DataEntryTypeEnum,
        year: Optional[int] = None,
    ) -> None:
        """Bulk delete factors by data entry type and optional year.

        Args:
            data_entry_type_id: Data entry type filter
            year: Optional year filter. If provided, only deletes factors for that year.
                  If not provided, deletes all factors for the data entry type.
        """
        if year is not None:
            factor_ids = await self.repo.list_id_by_data_entry_type_and_year(
                data_entry_type_id=data_entry_type_id,
                year=year,
            )
            logger.info(
                f"Deleting {len(factor_ids)} factors for "
                f"data_entry_type={data_entry_type_id}, year={year}"
            )
        else:
            factor_ids = await self.repo.list_id_by_data_entry_type(
                data_entry_type_id=data_entry_type_id,
            )
            logger.info(
                f"Deleting {len(factor_ids)} factors for "
                f"data_entry_type={data_entry_type_id} (all years)"
            )

        await self.repo.bulk_delete(factor_ids)

    async def find_modules_for_recalculation(self, factor_id: int) -> List[int]:
        """Find CarbonReportModule IDs that used the given factor.

        Queries DataEntryEmission rows where primary_factor_id matches, then
        returns the distinct carbon_report_module_ids of the linked DataEntries.

        Args:
            factor_id: The ID of the factor that changed.

        Returns:
            List of distinct carbon_report_module_id values that reference this factor.
        """
        stmt = (
            select(col(DataEntry.carbon_report_module_id))
            .join(
                DataEntryEmission,
                col(DataEntry.id) == col(DataEntryEmission.data_entry_id),
            )
            .where(col(DataEntryEmission.primary_factor_id) == factor_id)
            .distinct()
        )
        result = await self.session.exec(stmt)
        return [row for row in result.all() if row is not None]
