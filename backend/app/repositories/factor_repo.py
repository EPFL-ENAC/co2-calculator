"""Repository for generic factors."""

from typing import Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionTypeEnum
from app.models.factor import Factor


class FactorRepository:
    """Repository for factor CRUD operations and lookups."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Data entry type ID for emission factors (energy_mix)
    EMISSION_FACTOR_DATA_ENTRY_TYPE_ID = DataEntryTypeEnum.energy_mix.value

    async def get(self, id: int) -> Optional[Factor]:
        """Get factor by ID."""
        stmt = select(Factor).where(col(Factor.id) == id)
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_electricity_factor(self) -> Optional[Factor]:
        """Get the electricity factor."""
        stmt = select(Factor).where(
            col(Factor.data_entry_type_id) == DataEntryTypeEnum.energy_mix.value,
        )

        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_current_factor(
        self,
        emission_type_id: EmissionTypeEnum,
        data_entry_type_id: DataEntryTypeEnum,
    ) -> Optional[Factor]:
        """
        Get the current (valid_to IS NULL) factor for given criteria.

        Args:
            emission_type_id: Emission type filter
            data_entry_type_id: Data entry type filter
        """
        stmt = select(Factor).where(
            col(Factor.emission_type_id) == emission_type_id,
            col(Factor.data_entry_type_id) == data_entry_type_id,
        )

        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def create(self, factor: Factor) -> Factor:
        """Create a new factor."""
        self.session.add(factor)
        await self.session.flush()
        await self.session.refresh(factor)
        return factor

    async def bulk_create(self, factors: List[Factor]) -> List[Factor]:
        """Bulk create factors."""
        self.session.add_all(factors)
        await self.session.flush()
        for factor in factors:
            await self.session.refresh(factor)
        return factors

    async def update(self, factor_id: int, update_data: Dict) -> Optional[Factor]:
        """Update an existing factor."""
        factor = await self.get(factor_id)
        if not factor:
            return None

        for field, value in update_data.items():
            setattr(factor, field, value)

        await self.session.flush()
        await self.session.refresh(factor)
        return factor

    async def delete(self, factor_id: int) -> bool:
        """Delete a factor by ID."""
        factor = await self.get(factor_id)
        if not factor:
            return False

        await self.session.delete(factor)
        await self.session.flush()
        return True

    async def bulk_delete(self, factor_ids: list[int]) -> None:
        """Bulk delete factors by IDs."""
        stmt = select(Factor).where(col(Factor.id).in_(factor_ids))
        result = await self.session.exec(stmt)
        factors_to_delete = result.all()

        for factor in factors_to_delete:
            await self.session.delete(factor)

        await self.session.flush()

    async def list_id_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
    ) -> List[int]:
        """List all factors for a family."""
        stmt = select(Factor.id).where(
            col(Factor.data_entry_type_id) == data_entry_type_id
        )

        result = await self.session.exec(stmt)
        return [id for id in result.all() if id is not None]

    async def list_by_data_entry_type(
        self,
        data_entry_type_id: DataEntryTypeEnum,
    ) -> List[Factor]:
        """List all factors for a family."""
        stmt = select(Factor).where(
            col(Factor.data_entry_type_id) == data_entry_type_id
        )

        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_class_subclass_map(
        self, data_entry_type: DataEntryTypeEnum
    ) -> Dict[str, List[str]]:
        """
        Return a mapping of equipment_class -> list of subclasses.

        Mimics legacy PowerFactorRepository.get_class_subclass_map.
        """
        stmt = select(
            Factor.classification["kind"].as_string(),
            Factor.classification["subkind"].as_string(),
        ).where(col(Factor.data_entry_type_id) == data_entry_type.value)

        result = await self.session.exec(stmt)
        factors = result.all()

        mapping: Dict[str, List[str]] = {}

        for factor in factors:
            equipment_class = factor[0]
            sub_class = factor[1]

            if not equipment_class:
                continue

            if equipment_class not in mapping:
                mapping[equipment_class] = []

            if sub_class and sub_class not in mapping[equipment_class]:
                mapping[equipment_class].append(sub_class)

        # Sort subclasses
        for key in mapping:
            mapping[key].sort()

        return dict(sorted(mapping.items()))

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

    async def get_by_classification(
        self,
        data_entry_type: DataEntryTypeEnum,
        kind: str,
        subkind: Optional[str] = None,
    ) -> Optional[Factor]:
        # First try exact match with subkind
        if subkind:
            stmt = select(Factor).where(
                col(Factor.data_entry_type_id) == data_entry_type.value,
                Factor.classification["kind"].as_string() == kind,
                Factor.classification["subkind"].as_string() == subkind,
            )
            result = await self.session.exec(stmt)
            factor = result.one_or_none()
            if factor:
                return factor

        # Fallback to kind-only match (no subkind)
        stmt = select(Factor).where(
            col(Factor.data_entry_type_id) == data_entry_type.value,
            Factor.classification["kind"].as_string() == kind,
            Factor.classification["subkind"].as_string().is_(None),
        )
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_factor(
        self,
        data_entry_type: DataEntryTypeEnum,
        fallbacks: Optional[dict[str, str]] = None,
        **classification: str,
    ) -> Optional[Factor]:
        """
        Generic factor lookup with dynamic classification filters.

        Args:
            data_entry_type: The data entry type to filter on
            fallbacks: Optional dict of fallback values for classification keys
                       e.g. {"country_code": "RoW"} to try RoW if exact match fails
            **classification: Classification filters (kind, subkind, category,
                              country_code, etc.)

        Examples:
            # Flight factor
            get_factor(DataEntryTypeEnum.trips, kind="plane", category="short_haul")

            # Train factor with RoW fallback
            get_factor(
                DataEntryTypeEnum.trips,
                fallbacks={"country_code": "RoW"},
                kind=TransportModeEnum.train.value,
                country_code="FR",
            )
        """
        conditions = [col(Factor.data_entry_type_id) == data_entry_type.value]
        for key, value in classification.items():
            conditions.append(Factor.classification[key].as_string() == value)

        stmt = select(Factor).where(*conditions)
        result = await self.session.exec(stmt)
        factor = result.one_or_none()

        if factor or not fallbacks:
            return factor

        # Try with fallback values
        for key, fallback_value in fallbacks.items():
            if key in classification:
                classification[key] = fallback_value

        conditions = [col(Factor.data_entry_type_id) == data_entry_type.value]
        for key, value in classification.items():
            conditions.append(Factor.classification[key].as_string() == value)

        stmt = select(Factor).where(*conditions)
        result = await self.session.exec(stmt)
        return result.one_or_none()

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
