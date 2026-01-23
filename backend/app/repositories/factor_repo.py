"""Repository for generic factors."""

from typing import Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry_type import DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum
from app.models.factor import Factor


class FactorRepository:
    """Repository for factor CRUD operations and lookups."""

    # Data entry type ID for emission factors (energy_mix)
    EMISSION_FACTOR_DATA_ENTRY_TYPE_ID = 100

    async def get(self, session: AsyncSession, id: int) -> Optional[Factor]:
        """Get factor by ID."""
        stmt = select(Factor).where(col(Factor.id) == id)
        result = await session.exec(stmt)
        return result.one_or_none()

    async def get_current_factor(
        self,
        session: AsyncSession,
        emission_type_id: EmissionTypeEnum,
        data_entry_type_id: DataEntryTypeEnum,
    ) -> Optional[Factor]:
        """
        Get the current (valid_to IS NULL) factor for given criteria.

        Args:
            session: Database session
            emission_type_id: Emission type filter
            data_entry_type_id: Data entry type filter
        """
        stmt = select(Factor).where(
            col(Factor.emission_type_id) == emission_type_id,
            col(Factor.data_entry_type_id) == data_entry_type_id,
        )

        result = await session.exec(stmt)
        return result.one_or_none()

    async def create(self, session: AsyncSession, factor: Factor) -> Factor:
        """Create a new factor."""
        session.add(factor)
        await session.flush()
        await session.refresh(factor)
        return factor

    async def update(
        self, session: AsyncSession, factor_id: int, update_data: Dict
    ) -> Optional[Factor]:
        """Update an existing factor."""
        factor = await self.get(session, factor_id)
        if not factor:
            return None

        for field, value in update_data.items():
            setattr(factor, field, value)

        await session.flush()
        await session.refresh(factor)
        return factor

    async def delete(self, session: AsyncSession, factor_id: int) -> bool:
        """Delete a factor by ID."""
        factor = await self.get(session, factor_id)
        if not factor:
            return False

        await session.delete(factor)
        await session.flush()
        return True

    # async def get_by_id(
    #     self, session: AsyncSession, factor_id: int
    # ) -> Optional[Factor]:
    #     """Get factor by ID."""
    #     stmt = select(Factor).where(col(Factor.id) == factor_id)
    #     result = await session.exec(stmt)
    #     return result.one_or_none()

    # async def get_current_factor(
    #     self,
    #     session: AsyncSession,
    #     factor_family: str,
    #     variant_type_id: Optional[int] = None,
    #     classification: Optional[Dict] = None,
    # ) -> Optional[Factor]:
    #     """
    #     Get the current (valid_to IS NULL) factor for given criteria.

    #     Args:
    #         session: Database session
    #         factor_family: Factor family (e.g., 'power', 'headcount')
    #         variant_type_id: Optional variant type filter
    #         classification: Optional classification dict to match

    #     Returns:
    #         Current factor if found, None otherwise
    #     """
    #     stmt = select(Factor).where(
    #         col(Factor.factor_family) == factor_family,
    #         col(Factor.valid_to).is_(None),
    #     )

    #     if variant_type_id is not None:
    #         stmt = stmt.where(col(Factor.variant_type_id) == variant_type_id)

    #     result = await session.exec(stmt)
    #     factors = result.all()

    #     if not classification:
    #         return factors[0] if factors else None

    #     # Filter by classification match
    #     for factor in factors:
    #         factor_cls = factor.classification or {}
    #         if all(factor_cls.get(k) == v for k, v in classification.items()):
    #             return factor

    #     return None

    # async def get_power_factor(
    #     self,
    #     session: AsyncSession,
    #     variant_type_id: int,
    #     equipment_class: str,
    #     sub_class: Optional[str] = None,
    # ) -> Optional[Factor]:
    #     """
    #     Get power factor with classification matching (class/sub_class).

    #     Mimics the legacy PowerFactorRepository.get_power_factor behavior.
    #     """
    #     stmt = select(Factor).where(
    #         col(Factor.factor_family) == "power",
    #         col(Factor.variant_type_id) == variant_type_id,
    #         col(Factor.valid_to).is_(None),
    #     )

    #     result = await session.exec(stmt)
    #     factors = result.all()

    #     # First try exact match with sub_class
    #     if sub_class:
    #         for factor in factors:
    #             cls = factor.classification or {}
    #             if (
    #                 cls.get("class") == equipment_class
    #                 and cls.get("sub_class") == sub_class
    #             ):
    #                 return factor

    #     # Fallback to class-only match
    #     for factor in factors:
    #         cls = factor.classification or {}
    #         if cls.get("class") == equipment_class and not cls.get("sub_class"):
    #             return factor

    #     return None

    # async def get_emission_factor(
    #     self,
    #     session: AsyncSession,
    #     region: str = "CH",
    # ) -> Optional[Factor]:
    #     """
    #     Get the current emission factor for a given region.

    #     Args:
    #         session: Database session
    #         region: Geographic region code (default: 'CH' for Switzerland)

    #     Returns:
    #         Current emission factor if found, None otherwise

    #     Example:
    #         factor = await repo.get_emission_factor(session, region='CH')
    #         kg_co2eq_per_kwh = factor.values.get('kg_co2eq_per_kwh')  # e.g., 0.128
    #     """
    #     stmt = select(Factor).where(
    #         col(Factor.factor_family) == "emission",
    #         col(Factor.data_entry_type_id) == self.EMISSION_FACTOR_DATA_ENTRY_TYPE_ID,
    #         col(Factor.valid_to).is_(None),  # Current version only
    #     )

    #     result = await session.exec(stmt)
    #     factors = result.all()

    #     # Filter by region in classification
    #     for factor in factors:
    #         cls = factor.classification or {}
    #         if cls.get("region") == region:
    #             return factor

    #     return None

    # async def get_emission_factor_value(
    #     self,
    #     session: AsyncSession,
    #     region: str = "CH",
    # ) -> Optional[float]:
    #     """
    #     Get the emission factor value (kgCO2eq/kWh) for a region.

    #     Convenience method that returns just the value for calculations.

    #     Args:
    #         session: Database session
    #         region: Geographic region code (default: 'CH')

    #     Returns:
    #         Emission factor value in kgCO2eq/kWh, or None if not found
    #     """
    #     factor = await self.get_emission_factor(session, region)
    #     if factor:
    #         return factor.values.get("kg_co2eq_per_kwh")
    #     return None

    async def list_by_data_entry_type(
        self,
        session: AsyncSession,
        data_entry_type_id: DataEntryTypeEnum,
        include_expired: bool = False,
    ) -> List[Factor]:
        """List all factors for a family."""
        stmt = select(Factor).where(
            col(Factor.data_entry_type_id) == data_entry_type_id
        )

        result = await session.exec(stmt)
        return list(result.all())

    # async def list_power_classes(
    #     self, session: AsyncSession, variant_type_id: int
    # ) -> List[str]:
    #     """List distinct equipment classes for power factors."""
    #     stmt = (
    #         select(Factor)
    #         .where(col(Factor.factor_family) == "power")
    #         .where(col(Factor.variant_type_id) == variant_type_id)
    #         .where(col(Factor.valid_to).is_(None))
    #     )

    #     result = await session.exec(stmt)
    #     factors = result.all()

    #     classes = set()
    #     for factor in factors:
    #         cls = factor.classification or {}
    #         if cls.get("class"):
    #             classes.add(cls["class"])

    #     return sorted(list(classes))

    # async def list_power_subclasses(
    #     self, session: AsyncSession, variant_type_id: int, equipment_class: str
    # ) -> List[str]:
    #     """List distinct sub_classes for a given class."""
    #     stmt = (
    #         select(Factor)
    #         .where(col(Factor.factor_family) == "power")
    #         .where(col(Factor.variant_type_id) == variant_type_id)
    #         .where(col(Factor.valid_to).is_(None))
    #     )

    #     result = await session.exec(stmt)
    #     factors = result.all()

    #     subclasses = set()
    #     for factor in factors:
    #         cls = factor.classification or {}
    #         if cls.get("class") == equipment_class and cls.get("sub_class"):
    #             subclasses.add(cls["sub_class"])

    #     return sorted(list(subclasses))

    # async def get_class_subclass_map(
    #     self, session: AsyncSession, variant_type_id: int
    # ) -> Dict[str, List[str]]:
    #     """
    #     Return a mapping of equipment_class -> list of subclasses.

    #     Mimics legacy PowerFactorRepository.get_class_subclass_map.
    #     """
    #     stmt = (
    #         select(Factor)
    #         .where(col(Factor.factor_family) == "power")
    #         .where(col(Factor.variant_type_id) == variant_type_id)
    #         .where(col(Factor.valid_to).is_(None))
    #     )

    #     result = await session.exec(stmt)
    #     factors = result.all()

    #     mapping: Dict[str, List[str]] = {}

    #     for factor in factors:
    #         cls = factor.classification or {}
    #         equipment_class = cls.get("class")
    #         sub_class = cls.get("sub_class")

    #         if not equipment_class:
    #             continue

    #         if equipment_class not in mapping:
    #             mapping[equipment_class] = []

    #         if sub_class and sub_class not in mapping[equipment_class]:
    #             mapping[equipment_class].append(sub_class)

    #     # Sort subclasses
    #     for key in mapping:
    #         mapping[key].sort()

    #     return dict(sorted(mapping.items()))

    # async def create(self, session: AsyncSession, factor: Factor) -> Factor:
    #     """Create a new factor."""
    #     session.add(factor)
    #     await session.flush()
    #     await session.refresh(factor)
    #     return factor

    # async def expire_factor(
    #     self, session: AsyncSession, factor_id: int
    # ) -> Optional[Factor]:
    #     """Mark a factor as expired (set valid_to to now)."""
    #     from datetime import datetime, timezone

    #     factor = await self.get_by_id(session, factor_id)
    #     if factor:
    #         factor.valid_to = datetime.now(timezone.utc)
    #         await session.flush()
    #         await session.refresh(factor)
    #     return factor

    # async def find_affected_emissions(
    #     self, session: AsyncSession, factor_id: int
    # ) -> List[int]:
    #     """
    #     Find all current module_emission IDs that used this factor.

    #     Used for batch recalculation when a factor changes.

    #     Note: Uses primary_factor_id FK on module_emissions (no join table).
    #     """
    #     from app.models.module_emission import ModuleEmission

    #     stmt = (
    #         select(ModuleEmission.id)
    #         .where(
    #             ModuleEmission.primary_factor_id == factor_id,
    #             ModuleEmission.is_current == True,  # noqa: E712
    #         )
    #         .distinct()
    #     )

    #     result = await session.exec(stmt)
    #     return list(result.all())

    # async def find_modules_for_recalculation(
    #     self, session: AsyncSession, factor_id: int
    # ) -> List[int]:
    #     """
    #     Find all module IDs that need recalculation when a factor changes.

    #     Note: Uses primary_factor_id FK on module_emissions (no join table).
    #     """
    #     from app.models.module_emission import ModuleEmission

    #     stmt = (
    #         select(ModuleEmission.module_id)
    #         .where(
    #             ModuleEmission.primary_factor_id == factor_id,
    #             ModuleEmission.is_current == True,  # noqa: E712
    #         )
    #         .distinct()
    #     )

    #     result = await session.exec(stmt)
    #     return list(result.all())
