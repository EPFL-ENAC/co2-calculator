"""Generic emission calculation service with strategy pattern.

Supports different calculation strategies per module type:
- Equipment: power-based energy emissions
- Headcount: FTE-based multi-emission (food, waste, transport, grey_energy)
- Future: flights, cloud, etc.

Emission factors (factor_family='emission') are now stored in the unified
factors table. For traceability, emission factor info is stored in the
meta column of data_entry_emissions rather than as a FK.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.emission_type import EmissionType
from app.models.factor import Factor
from app.models.module import Module
from app.models.module_emission import ModuleEmission
from app.repositories.factor_repo import FactorRepository
from app.schemas.module_emission import (
    EmissionCalculationResult,
    ModuleEmissionResponse,
)

logger = get_logger(__name__)
settings = get_settings()


class EmissionCalculationStrategy(ABC):
    """Abstract base class for emission calculation strategies."""

    @property
    @abstractmethod
    def module_type_name(self) -> str:
        """Module type this strategy handles."""
        pass

    @property
    @abstractmethod
    def formula_version(self) -> str:
        """Version identifier for this calculation formula."""
        pass

    @abstractmethod
    async def get_factors(
        self,
        session: AsyncSession,
        module: Module,
    ) -> List[Factor]:
        """Retrieve relevant factors for this module."""
        pass

    @abstractmethod
    async def calculate(
        self,
        session: AsyncSession,
        module: Module,
        factors: List[Factor],
        emission_types: Dict[str, EmissionType],
        emission_factor: Optional[Factor] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate emissions for a module.

        Returns list of emission dicts, each with:
        - emission_type_id
        - kg_co2eq
        - metadata (includes emission_factor info for traceability)
        - input_snapshot
        - factor_id (optional)
        """
        pass


class EquipmentCalculationStrategy(EmissionCalculationStrategy):
    """Calculation strategy for equipment (power-based energy emissions)."""

    @property
    def module_type_name(self) -> str:
        return "equipment-electric-consumption"

    @property
    def formula_version(self) -> str:
        return "v1_power_linear"

    async def get_factors(
        self,
        session: AsyncSession,
        module: Module,
    ) -> List[Factor]:
        """Get power factor for equipment based on class/sub_class."""
        from sqlmodel import select

        # Extract classification from module data
        data = module.data or {}
        equipment_class = data.get("equipment_class")
        sub_class = data.get("sub_class")

        if not equipment_class:
            logger.warning(f"Module {module.id} missing equipment_class")
            return []

        # Query factor by variant + classification
        stmt = select(Factor).where(
            Factor.factor_family == "power",
            Factor.variant_type_id == module.variant_type_id,
            Factor.valid_to.is_(None),  # Current version
        )

        result = await session.exec(stmt)
        factors = result.all()

        # Filter by classification match
        matched = []
        for factor in factors:
            cls = factor.classification or {}
            if cls.get("class") == equipment_class:
                # Prefer exact sub_class match
                if sub_class and cls.get("sub_class") == sub_class:
                    return [factor]  # Exact match
                elif not cls.get("sub_class"):
                    matched.append(factor)  # Class-level fallback

        return matched[:1] if matched else []

    async def calculate(
        self,
        session: AsyncSession,
        module: Module,
        factors: List[Factor],
        emission_types: Dict[str, EmissionType],
        emission_factor: Optional[Factor] = None,
    ) -> List[Dict[str, Any]]:
        """Calculate energy emission for equipment."""
        if not factors:
            logger.warning(f"No power factor found for module {module.id}")
            return []

        factor = factors[0]
        values = factor.values or {}
        active_power_w = values.get("active_power_w", 0)
        standby_power_w = values.get("standby_power_w", 0)

        # Get usage from module data
        data = module.data or {}
        act_usage = data.get("active_usage_pct", 0)
        pas_usage = data.get("passive_usage_pct", 0)
        status = data.get("status", "In service")

        # Get emission factor value from Factor or fallback to settings
        emission_factor_value = settings.EMISSION_FACTOR_SWISS_MIX
        emission_factor_region = "CH"
        emission_factor_id = None

        if emission_factor:
            ef_values = emission_factor.values or {}
            emission_factor_value = ef_values.get(
                "kg_co2eq_per_kwh", settings.EMISSION_FACTOR_SWISS_MIX
            )
            ef_cls = emission_factor.classification or {}
            emission_factor_region = ef_cls.get("region", "CH")
            emission_factor_id = emission_factor.id

        # Calculate only if in service
        if status != "In service":
            kg_co2eq = 0.0
            annual_kwh = 0.0
        else:
            # Weekly energy in Watt-hours
            weekly_wh = (act_usage * active_power_w) + (pas_usage * standby_power_w)
            # Annual kWh
            annual_kwh = (weekly_wh * settings.WEEKS_PER_YEAR) / 1000
            # CO2 emissions
            kg_co2eq = annual_kwh * emission_factor_value

        # Use 'equipment' emission type (not 'energy' - that's for emission factors)
        equipment_type = emission_types.get("equipment")
        if not equipment_type:
            logger.error("Emission type 'equipment' not found")
            return []

        # Get subcategory from variant_type (scientific, it, admin)
        from sqlmodel import select
        from app.models.variant_type import VariantType

        stmt = select(VariantType).where(VariantType.id == module.variant_type_id)
        result = await session.exec(stmt)
        variant_type = result.first()
        subcategory = variant_type.name if variant_type else "other"

        # Build factors_used array
        factors_used = [
            {
                "id": factor.id,
                "role": "primary",
                "factor_family": "power",
                "values": factor.values,
            }
        ]
        if emission_factor:
            factors_used.append(
                {
                    "id": emission_factor.id,
                    "role": "emission",
                    "factor_family": "emission",
                    "values": emission_factor.values,
                }
            )

        return [
            {
                "emission_type_id": equipment_type.id,
                "primary_factor_id": factor.id,
                "subcategory": subcategory,
                "kg_co2eq": round(kg_co2eq, 2),
                "metadata": {
                    "annual_kwh": round(annual_kwh, 2),
                    "active_power_w": active_power_w,
                    "standby_power_w": standby_power_w,
                    "emission_factor_region": emission_factor_region,
                    "factors_used": factors_used,
                },
                "input_snapshot": {
                    "active_usage_pct": act_usage,
                    "passive_usage_pct": pas_usage,
                    "active_power_w": active_power_w,
                    "standby_power_w": standby_power_w,
                    "emission_factor_value": emission_factor_value,
                    "status": status,
                },
            }
        ]


class HeadcountCalculationStrategy(EmissionCalculationStrategy):
    """Calculation strategy for headcount (FTE-based multi-emissions)."""

    @property
    def module_type_name(self) -> str:
        return "my-lab"

    @property
    def formula_version(self) -> str:
        return "v1_fte_linear"

    async def get_factors(
        self,
        session: AsyncSession,
        module: Module,
    ) -> List[Factor]:
        """Get headcount factor for variant (student/member)."""
        from sqlmodel import select

        stmt = select(Factor).where(
            Factor.factor_family == "headcount",
            Factor.variant_type_id == module.variant_type_id,
            Factor.valid_to.is_(None),
        )

        result = await session.exec(stmt)
        factors = result.all()
        return list(factors)

    async def calculate(
        self,
        session: AsyncSession,
        module: Module,
        factors: List[Factor],
        emission_types: Dict[str, EmissionType],
        emission_factor: Optional[Factor] = None,
    ) -> List[Dict[str, Any]]:
        """Calculate 4 emissions for headcount (food, waste, transport, grey_energy)."""
        if not factors:
            logger.warning(f"No headcount factor found for module {module.id}")
            return []

        factor = factors[0]
        values = factor.values or {}

        # Get FTE from module data
        data = module.data or {}
        fte = data.get("fte", 0)

        emissions = []

        # Map factor value keys to emission type codes
        emission_mapping = {
            "food_kg": "food",
            "waste_kg": "waste",
            "transport_kg": "transport",
            "grey_energy_kg": "grey_energy",
        }

        for value_key, emission_code in emission_mapping.items():
            kg_per_fte = values.get(value_key, 0)
            kg_co2eq = fte * kg_per_fte

            emission_type = emission_types.get(emission_code)
            if not emission_type:
                logger.warning(f"Emission type '{emission_code}' not found")
                continue

            # Build factors_used array (headcount uses only 1 factor per emission)
            factors_used = [
                {
                    "id": factor.id,
                    "role": "primary",
                    "factor_family": "headcount",
                    "values": {value_key: kg_per_fte},
                }
            ]

            emissions.append(
                {
                    "emission_type_id": emission_type.id,
                    "primary_factor_id": factor.id,
                    "subcategory": emission_code,  # food, waste, transport, grey_energy
                    "kg_co2eq": round(kg_co2eq, 2),
                    "metadata": {
                        "fte": fte,
                        "kg_per_fte": kg_per_fte,
                        "emission_code": emission_code,
                        "factors_used": factors_used,
                    },
                    "input_snapshot": {
                        "fte": fte,
                        value_key: kg_per_fte,
                    },
                }
            )

        return emissions


class EmissionCalculationService:
    """
    Service for calculating emissions across all module types.

    Uses strategy pattern to delegate to module-specific calculators.
    """

    def __init__(self):
        self._strategies: Dict[str, EmissionCalculationStrategy] = {}
        self._strategies_by_type_id: Dict[int, EmissionCalculationStrategy] = {}

        # Register default strategies
        self.register_strategy(EquipmentCalculationStrategy())
        self.register_strategy(HeadcountCalculationStrategy())

    def register_strategy(self, strategy: EmissionCalculationStrategy) -> None:
        """Register a calculation strategy for a module type."""
        self._strategies[strategy.module_type_name] = strategy

    def register_strategy_by_type_id(
        self, module_type_id: int, strategy: EmissionCalculationStrategy
    ) -> None:
        """Register strategy by module type ID."""
        self._strategies_by_type_id[module_type_id] = strategy

    async def _get_emission_types(
        self, session: AsyncSession
    ) -> Dict[str, EmissionType]:
        """Load all emission types indexed by code."""
        from sqlmodel import select

        stmt = select(EmissionType)
        result = await session.exec(stmt)
        types = result.all()
        return {t.code: t for t in types}

    async def _get_strategy_for_module(
        self,
        session: AsyncSession,
        module: Module,
    ) -> Optional[EmissionCalculationStrategy]:
        """Get calculation strategy for a module."""
        # First try by type ID
        if module.module_type_id in self._strategies_by_type_id:
            return self._strategies_by_type_id[module.module_type_id]

        # Then look up module type name
        from sqlmodel import select
        from app.models.module_type import ModuleType

        stmt = select(ModuleType).where(ModuleType.id == module.module_type_id)
        result = await session.exec(stmt)
        module_type = result.first()

        if module_type and module_type.name in self._strategies:
            # Cache for future lookups
            self._strategies_by_type_id[module.module_type_id] = self._strategies[
                module_type.name
            ]
            return self._strategies[module_type.name]

        return None

    async def calculate_for_module(
        self,
        session: AsyncSession,
        module: Module,
        region: str = "CH",
        persist: bool = True,
    ) -> EmissionCalculationResult:
        """
        Calculate emissions for a single module.

        Args:
            session: Database session
            module: Module to calculate for
            region: Geographic region for emission factor lookup (default: 'CH')
            persist: Whether to persist results to database

        Returns:
            EmissionCalculationResult with all calculated emissions
        """
        strategy = await self._get_strategy_for_module(session, module)
        if not strategy:
            logger.warning(f"No strategy found for module type {module.module_type_id}")
            return EmissionCalculationResult(
                module_id=module.id or 0,
                emissions=[],
                total_kg_co2eq=0,
                calculated_at=datetime.now(timezone.utc),
            )

        # Load emission types
        emission_types = await self._get_emission_types(session)

        # Get factors for the module type
        factors = await strategy.get_factors(session, module)

        # Get emission factor from unified factors table
        factor_repo = FactorRepository()
        emission_factor = await factor_repo.get_emission_factor(session, region)

        # Calculate
        results = await strategy.calculate(
            session,
            module,
            factors,
            emission_types,
            emission_factor,
        )

        # Persist if requested
        emissions: List[ModuleEmissionResponse] = []
        now = datetime.now(timezone.utc)

        for result in results:
            if persist:
                # Mark previous emissions as not current
                from sqlmodel import select, update

                stmt = (
                    update(ModuleEmission)
                    .where(
                        ModuleEmission.module_id == module.id,
                        ModuleEmission.emission_type_id == result["emission_type_id"],
                        ModuleEmission.is_current == True,  # noqa: E712
                    )
                    .values(is_current=False)
                )
                await session.exec(stmt)  # type: ignore

                # Create new emission with primary_factor_id and subcategory
                # All factors stored in meta.factors_used array
                emission = ModuleEmission(
                    module_id=module.id,
                    emission_type_id=result["emission_type_id"],
                    primary_factor_id=result.get("primary_factor_id"),
                    subcategory=result.get("subcategory"),
                    kg_co2eq=result["kg_co2eq"],
                    meta=result.get("metadata", {}),
                    formula_version=strategy.formula_version,
                    computed_at=now,
                    is_current=True,
                )
                session.add(emission)
                await session.flush()

            # Build response
            emission_type = next(
                (
                    t
                    for t in emission_types.values()
                    if t.id == result["emission_type_id"]
                ),
                None,
            )
            emissions.append(
                ModuleEmissionResponse(
                    id=emission.id if persist else 0,
                    module_id=module.id or 0,
                    emission_type_id=result["emission_type_id"],
                    kg_co2eq=result["kg_co2eq"],
                    metadata=result.get("metadata", {}),
                    formula_version=strategy.formula_version,
                    computed_at=now,
                    is_current=True,
                    emission_type_code=emission_type.code if emission_type else None,
                    emission_type_label=emission_type.label if emission_type else None,
                )
            )

        if persist:
            await session.commit()

        total = sum(e.kg_co2eq for e in emissions)

        return EmissionCalculationResult(
            module_id=module.id or 0,
            emissions=emissions,
            total_kg_co2eq=round(total, 2),
            calculated_at=now,
        )

    async def recalculate_for_modules(
        self,
        session: AsyncSession,
        module_ids: List[int],
        region: str = "CH",
    ) -> List[EmissionCalculationResult]:
        """
        Recalculate emissions for multiple modules.

        Args:
            session: Database session
            module_ids: List of module IDs to recalculate
            region: Geographic region for emission factor lookup (default: 'CH')

        Returns:
            List of calculation results
        """
        from sqlmodel import select

        stmt = select(Module).where(Module.id.in_(module_ids))
        result = await session.exec(stmt)
        modules = result.all()

        results = []
        for module in modules:
            calc_result = await self.calculate_for_module(
                session,
                module,
                region,
                persist=True,
            )
            results.append(calc_result)

        return results


# Singleton instance
_emission_calc_service: Optional[EmissionCalculationService] = None


def get_emission_calculation_service() -> EmissionCalculationService:
    """Get or create the emission calculation service singleton."""
    global _emission_calc_service
    if _emission_calc_service is None:
        _emission_calc_service = EmissionCalculationService()
    return _emission_calc_service
