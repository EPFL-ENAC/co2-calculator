from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType, get_scope
from app.models.factor import Factor
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.factor_service import FactorService
from app.utils.data_entry_emission_type_map import resolve_emission_types

settings = get_settings()
logger = get_logger(__name__)


class DataEntryEmissionService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryEmissionRepository(session)

    async def prepare_create(
        self,
        data_entry: DataEntry | DataEntryResponse,
    ) -> list[DataEntryEmission]:
        """Prepare emission records for any data entry type.

        The handler attached to this data entry type owns:
        - which factors to look up (``resolve_factor_classification``)
        - how to compute kg_co2eq (``compute_kg_co2eq``)

        This method only orchestrates: resolve types → fetch factor
        → compute → build row. No branching on DataEntryType.

        Args:
            data_entry: Fully hydrated data entry with ``data_entry_type``.

        Returns:
            Ready-to-insert ``DataEntryEmission`` rows; empty on any failure.
        """
        if not data_entry or data_entry.data_entry_type is None:
            logger.error("DataEntry must have a data_entry_type.")
            return []

        emission_types = resolve_emission_types(
            data_entry.data_entry_type, data_entry.data
        )
        if emission_types is None:
            logger.warning(f"Unhandled type: {data_entry.data_entry_type}")
            return []
        if not emission_types:
            return []

        if data_entry.id is None:
            logger.error("DataEntry must have an ID before creating emissions.")
            return []

        handler = BaseModuleHandler.get_by_type(
            DataEntryTypeEnum(data_entry.data_entry_type)
        )
        factor_service = FactorService(self.session)
        results: list[DataEntryEmission] = []

        for emission_type in emission_types:
            # Handler knows HOW to find the right factor for this type+entry combo
            classification = handler.resolve_factor_classification(
                data_entry, emission_type
            )
            factor = await factor_service.get_by_classification(
                data_entry_type=data_entry.data_entry_type,
                kind=classification.kind,
                subkind=classification.subkind,
            )
            if not factor or not factor.values:
                logger.warning(
                    f"Missing factor for emission_type={emission_type.name!r} "
                    f"data_entry_id={data_entry.id!r}"
                )
                continue

            # Handler knows WHICH formula to apply
            kg_co2eq = handler.compute_kg_co2eq(data_entry.data, factor.values)
            if kg_co2eq is None:
                logger.error(
                    f"Formula returned None for emission_type={emission_type.name!r} "
                    f"data_entry_id={data_entry.id!r}"
                )
                continue

            results.append(
                DataEntryEmission(
                    data_entry_id=data_entry.id,
                    emission_type_id=emission_type.value,
                    primary_factor_id=factor.id,
                    scope=get_scope(emission_type),
                    kg_co2eq=kg_co2eq,
                    meta={
                        "factors_used": [{"id": factor.id, "values": factor.values}],
                        **data_entry.data,
                    },
                )
            )

        return results

    async def prepare_create_old(
        self, data_entry: DataEntryResponse | DataEntry
    ) -> list[DataEntryEmission]:
        """Prepare emissions for a data entry, if applicable.

        Returns a list of emissions (one per emission type).
        For member/student types, multiple rows are produced (one per emission type).
        For building also multiple rows can be produced
        For other types, typically a single row is produced.

        how it works:
            - resolve emission types based on data entry type and data
                (using the mapping in utils/data_entry_emission_type_map)
            - for each emission type, determine the relevant factors to use
                (e.g. primary factor from data entry, electricity factor
                    for scientific/it/other, category-specific factors for building)
            - calculate kg_co2eq using the appropriate formula for the data entry
                type and emission type
            - return list of DataEntryEmission objects with calculated kg_co2eq and
                relevant metadata
            - if any required data or factors are missing, log warnings and skip those
                emissions (returning None or empty list as appropriate)
            - formulas are implemented in separate methods and registered in a dict
                for clean organization
            - this method focuses on preparing the emission records; actual database
                creation is done in create() or bulk_create() methods
        """
        if not data_entry:
            return []
        if data_entry.data_entry_type is None:
            logger.error(
                "DataEntry must have a data_entry_type before creating emissions."
            )
            return []

        # Generic emission type resolution — no if/elif
        emission_types = resolve_emission_types(
            data_entry.data_entry_type, data_entry.data
        )
        if emission_types is None:
            logger.warning(f"Unhandled emission type: {data_entry.data_entry_type}")
            return []
        if not emission_types:
            return []  # e.g. energy_mix — intentionally no rows

        handler = BaseModuleHandler.get_by_type(
            DataEntryTypeEnum(data_entry.data_entry_type)
        )
        primary_factor_id = data_entry.data.get("primary_factor_id")
        if not primary_factor_id and handler.require_factor_to_match:
            return []

        factors: list[Factor] = []
        factor_service = FactorService(self.session)
        if primary_factor_id is not None:
            primary_factor = await factor_service.get(primary_factor_id)
            if not primary_factor:
                return []
            factors = [primary_factor]

        # Start of module specific retrieval of factors and calculation logic
        # Equipment types need electricity factor too
        if data_entry.data_entry_type in (
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.other,
        ):
            electricity_factor = await factor_service.get_electricity_factor()
            if electricity_factor:
                factors.append(electricity_factor)

        # For headcount types (member/student), emit one row per emission type
        # using the appropriate factor for each emission type
        if data_entry.data_entry_type in (
            DataEntryTypeEnum.member,
            DataEntryTypeEnum.student,
        ):
            return await self._prepare_headcount_emissions(
                data_entry, emission_types, factor_service
            )

        # One row per emission_type — scope derived from EMISSION_SCOPE
        # We should get the factor corresponding to the emission type
        # and compute the kg_co2eq based on the data entry data and factor values of
        # each emission type match factors
        # example of implementation for building!

        #  for category in ("heating", "cooling", "ventilation", "lighting"):
        #         factor = await factor_service.get_by_classification(
        #             data_entry_type=DataEntryTypeEnum.building,
        #             kind=building_name,
        #             subkind=category,
        #         )
        #         if factor:
        #             factors.append(factor)
        results = []
        for emission_type in emission_types:
            # returns the factors used
            emissions_value = await self._calculate_emissions(
                data_entry, factors=factors
            )
            if data_entry.id is None:
                logger.error("DataEntry must have an ID before creating emissions.")
                return []
            if emissions_value.get("kg_co2eq") is None:
                logger.error(
                    "No emissions calculated for DataEntry ID "
                    f"{data_entry.id}. Skipping emission record creation"
                    f" (factor_id={primary_factor_id})"
                )
                return [
                    DataEntryEmission(
                        data_entry_id=data_entry.id,
                        emission_type_id=emission_type.value,
                        primary_factor_id=primary_factor_id,
                        scope=get_scope(emission_type),
                        kg_co2eq=emissions_value.get("kg_co2eq"),
                        meta={**emissions_value},
                    )
                ]
        return results

    async def create(self, data_entry: DataEntryResponse) -> list[DataEntryEmission]:
        """Create emissions for a data entry, if applicable.

        Returns a list of created emission records.
        """
        emission_records = await self.prepare_create(data_entry)
        if not emission_records:
            return []

        created_emissions = await self.repo.bulk_create(emission_records)
        return created_emissions

    async def bulk_create(
        self, emission_records: list[DataEntryEmission]
    ) -> list[DataEntryEmission]:
        """Create emissions for multiple data entries, if applicable."""
        created_emissions = await self.repo.bulk_create(emission_records)
        return created_emissions

    async def upsert_by_data_entry(
        self, data_entry_response: DataEntryResponse
    ) -> list[DataEntryEmission] | None:
        """Create or update emissions for a data entry, if applicable.

        First deletes existing emissions for this data entry, then creates new ones.
        Returns the list of created/updated emissions.
        """
        # Prepare the emission records
        prepared_emissions = await self.prepare_create(data_entry_response)
        if not prepared_emissions:
            await self.repo.delete_by_data_entry_id(data_entry_response.id)
            await self.session.flush()
            return None

        # Delete existing emissions
        await self.repo.delete_by_data_entry_id(data_entry_response.id)

        # Create new emissions
        created_emissions = await self.repo.bulk_create(prepared_emissions)
        return created_emissions

    async def get_stats(
        self,
        carbon_report_module_id: int,
        aggregate_by: str = "emission_type_id",
        aggregate_field: str = "kg_co2eq",
    ) -> dict[str, float | None]:
        """Get aggregated emission statistics for a carbon report module."""
        stats = await self.repo.get_stats(
            carbon_report_module_id,
            aggregate_by,
            aggregate_field,
        )
        return stats

    async def get_stats_by_carbon_report_id(
        self,
        carbon_report_id: int,
    ) -> dict[str, float]:
        """Get validated emission totals per module for a carbon report."""
        return await self.repo.get_stats_by_carbon_report_id(
            carbon_report_id=carbon_report_id,
        )

    async def get_emission_breakdown(
        self,
        carbon_report_id: int,
    ) -> list[tuple[int, int, int | None, float | None]]:
        """Get emission breakdown by module, emission type, and scope.

        Returns list of (module_type_id, emission_type_id, scope, sum_kg_co2eq).
        """
        return await self.repo.get_emission_breakdown(
            carbon_report_id=carbon_report_id,
        )

    async def get_travel_stats_by_class(
        self,
        carbon_report_module_id: int,
    ) -> list[dict]:
        """Get travel emissions aggregated by category and cabin_class."""
        return await self.repo.get_travel_stats_by_class(
            carbon_report_module_id,
        )

    async def get_travel_evolution_over_time(
        self,
        unit_id: int,
    ) -> list[dict]:
        """Get travel emissions aggregated by year and category."""
        return await self.repo.get_travel_evolution_over_time(unit_id)

    # Dict of dataEntryTypeEnum , func to calculation formulas
    FORMULAS: dict[EmissionType, Callable] = {}

    # create a decorator to register formulas
    @classmethod
    def register_formula(cls, name: EmissionType):
        # should register only for leaf!
        def decorator(func):
            cls.FORMULAS[name] = func
            return func

        return decorator

    async def _prepare_headcount_emissions_old(
        self,
        data_entry: DataEntry | DataEntryResponse,
        emission_types: list[EmissionType],
        factor_service: FactorService,
    ) -> list[DataEntryEmission]:
        """Prepare emissions for member/student types (one row per emission type).

        Each emission type (food, waste, commuting, grey_energy) uses its own factor.
        The kg_co2eq is calculated as: fte × factor_value.kg_co2eq_per_fte

        Args:
            data_entry: The data entry (member or student)
            emission_types: List of emission types (food, waste, commuting, grey_energy)
            factor_service: FactorService for looking up factors

        Returns:
            List of DataEntryEmission objects (one per emission type)
        """
        emissions: list[DataEntryEmission] = []
        fte = data_entry.data.get("fte", 0)

        for emission_type in emission_types:
            # Look up the specific factor for this emission type
            factor = await factor_service.get_by_classification(
                data_entry_type=data_entry.data_entry_type,
                kind=emission_type.name,
                subkind=None,
            )

            if not factor or not factor.values:
                logger.warning(
                    f"Missing factor for emission_type={emission_type} "
                    f"for data_entry_id={data_entry.id}"
                )
                continue

            # Calculate kg_co2eq = fte × kg_co2eq_per_fte
            kg_co2eq_per_fte = factor.values.get("kg_co2eq_per_fte", 0)
            kg_co2eq = fte * kg_co2eq_per_fte

            emissions.append(
                DataEntryEmission(
                    data_entry_id=data_entry.id,
                    emission_type_id=emission_type.value,
                    primary_factor_id=factor.id,
                    scope=get_scope(emission_type),
                    kg_co2eq=kg_co2eq,
                    meta={
                        "fte": fte,
                        "kg_co2eq_per_fte": kg_co2eq_per_fte,
                    },
                )
            )

        return emissions

    async def _calculate_emissions(
        self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
    ) -> dict:
        """Placeholder method for emissions calculation logic."""
        # Implement actual calculation based on data_entry data
        if data_entry.data_entry_type is None:
            raise ValueError("Data entry type is required for emissions calculation")
        formula_func = self.FORMULAS.get(data_entry.data_entry_type)
        if formula_func:
            return await formula_func(self, data_entry, factors)
        else:
            raise ValueError(f"No formula registered for: {data_entry.data_entry_type}")
