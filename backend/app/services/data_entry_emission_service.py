from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionTypeEnum
from app.models.factor import Factor
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.factor_service import FactorService

settings = get_settings()
logger = get_logger(__name__)


class DataEntryEmissionService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryEmissionRepository(session)

    async def prepare_create(
        self, data_entry: DataEntryResponse | DataEntry
    ) -> DataEntryEmission | None:
        """Prepare emissions for a data entry, if applicable."""
        if not data_entry:
            return None
        if data_entry.data_entry_type is None:
            logger.error(
                "DataEntry must have a data_entry_type before creating emissions."
            )
            return None
        handler = BaseModuleHandler.get_by_type(
            DataEntryTypeEnum(data_entry.data_entry_type)
        )
        # TODO: Make generic for all types!!!
        # for cloud it's this key
        if data_entry.data_entry_type == DataEntryTypeEnum.external_clouds:
            emission_type = EmissionTypeEnum[
                data_entry.data.get("sub_kind") or "calcul"
            ]
        elif data_entry.data_entry_type == DataEntryTypeEnum.external_ai:
            emission_type = EmissionTypeEnum.ai_provider
        elif (
            data_entry.data_entry_type == DataEntryTypeEnum.scientific_equipment
            or data_entry.data_entry_type == DataEntryTypeEnum.it_equipment
            or data_entry.data_entry_type == DataEntryTypeEnum.consumable_accessories
            or data_entry.data_entry_type
            == DataEntryTypeEnum.biological_chemical_gaseous_product
            or data_entry.data_entry_type == DataEntryTypeEnum.services
            or data_entry.data_entry_type == DataEntryTypeEnum.vehicles
            or data_entry.data_entry_type == DataEntryTypeEnum.other_purchases
            or data_entry.data_entry_type == DataEntryTypeEnum.additional_purchases
        ):
            emission_type = EmissionTypeEnum.purchase
        elif data_entry.data_entry_type == DataEntryTypeEnum.trips:
            transport_mode = data_entry.data.get("transport_mode")
            if transport_mode is None:
                raise ValueError("transport_mode is required for trips")
            emission_type = EmissionTypeEnum[str(transport_mode)]
        elif data_entry.data_entry_type == DataEntryTypeEnum.process_emissions:
            emission_type = EmissionTypeEnum.process_emissions
        # for equipment?
        elif (
            data_entry.data_entry_type == DataEntryTypeEnum.scientific
            or data_entry.data_entry_type == DataEntryTypeEnum.it
            or data_entry.data_entry_type == DataEntryTypeEnum.other
        ):
            emission_type = EmissionTypeEnum.equipment
        else:
            d_type = data_entry.data_entry_type
            logger.info(f"DataEntry type {d_type} not handled for ")
            return None
        # END OF TODO: Make generic for all types!!!

        # Factor already resolved by handler
        primary_factor_id = data_entry.data.get("primary_factor_id")
        if not primary_factor_id and handler.require_factor_to_match:
            return None

        factors: list[Factor] = []
        factor_service = FactorService(self.session)
        # retrieve factors based on data_entry info and type
        if primary_factor_id is not None:
            primary_factor = await factor_service.get(primary_factor_id)
            if not primary_factor:
                return None
            factors = [primary_factor]

        # Start of module specific retrieval of factors and calculation logic
        # Placeholder for actual emissions calculation logic
        # Equipment types need electricity factor too
        if data_entry.data_entry_type in (
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.other,
        ):
            electricity_factor = await factor_service.get_electricity_factor()
            if electricity_factor:
                factors.append(electricity_factor)

        # returns the factors used
        emissions_value = await self._calculate_emissions(data_entry, factors=factors)
        if data_entry.id is None:
            logger.error("DataEntry must have an ID before creating emissions.")
            return None
        if emissions_value.get("kg_co2eq") is None:
            logger.error(
                "No emissions calculated for DataEntry ID "
                f"{data_entry.id}. Skipping emission record creation"
                f" (factor_id={primary_factor_id})"
            )
            return None
        subcategory = None  # TODO: should be an enum somwhere
        if data_entry.data_entry_type == DataEntryTypeEnum.trips:
            subcategory = data_entry.data.get("transport_mode")
        elif data_entry.data_entry_type == DataEntryTypeEnum.process_emissions:
            sub_cat = data_entry.data.get("sub_category")
            subcategory = sub_cat if sub_cat else data_entry.data.get("emitted_gas")
        elif data_entry.data_entry_type is not None:
            subcategory = DataEntryTypeEnum(data_entry.data_entry_type).name.title()
        emission_record = DataEntryEmission(
            data_entry_id=data_entry.id,
            emission_type_id=emission_type.value,
            primary_factor_id=primary_factor_id,
            subcategory=subcategory,  # TODO: should be an enum somwhere
            kg_co2eq=emissions_value.get("kg_co2eq"),
            meta={**emissions_value},
        )
        return emission_record

    async def create(self, data_entry: DataEntryResponse) -> DataEntryEmission | None:
        """Create emissions for a data entry, if applicable."""
        emission_record = await self.prepare_create(data_entry)
        if not emission_record:
            return None
        created_emission = await self.repo.create(emission_record)
        # await self.session.refresh(created_emission)

        return created_emission

    async def bulk_create(
        self, emission_records: list[DataEntryEmission]
    ) -> list[DataEntryEmission]:
        """Create emissions for multiple data entries, if applicable."""
        created_emissions = await self.repo.bulk_create(emission_records)
        return created_emissions

    async def upsert_by_data_entry(
        self, data_entry_response: DataEntryResponse
    ) -> DataEntryEmission | None:
        """Create or update emissions for a data entry, if applicable."""
        # Prepare the emission record
        prepared_emission = await self.prepare_create(data_entry_response)
        if prepared_emission is None:
            await self.repo.delete_by_data_entry_id(data_entry_response.id)
            await self.session.flush()
            return None

        # Check if emission already exists
        existing_emission = await self.repo.get_by_data_entry_id(data_entry_response.id)
        if existing_emission is None:
            # Create new emission
            created_emission = await self.repo.create(prepared_emission)
            return created_emission
        else:
            # Update existing emission
            existing_emission.kg_co2eq = prepared_emission.kg_co2eq
            existing_emission.primary_factor_id = prepared_emission.primary_factor_id
            existing_emission.meta = prepared_emission.meta

            updated_emission = await self.repo.update(existing_emission)
            return updated_emission

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
    ) -> list[tuple[int, int, str | None, float | None]]:
        """Get emission breakdown by module, emission type, and subcategory."""
        return await self.repo.get_emission_breakdown(
            carbon_report_id=carbon_report_id,
        )

    async def get_travel_stats_by_class(
        self,
        carbon_report_module_id: int,
    ) -> list[dict]:
        """Get travel emissions aggregated by transport_mode and cabin_class."""
        return await self.repo.get_travel_stats_by_class(
            carbon_report_module_id,
        )

    async def get_travel_evolution_over_time(
        self,
        unit_id: int,
    ) -> list[dict]:
        """Get travel emissions aggregated by year and transport_mode."""
        return await self.repo.get_travel_evolution_over_time(unit_id)

    # Dict of dataEntryTypeEnum , func to calculation formulas
    FORMULAS: dict[DataEntryTypeEnum, Callable] = {}

    # create a decorator to register formulas
    @classmethod
    def register_formula(cls, name: DataEntryTypeEnum):
        def decorator(func):
            cls.FORMULAS[name] = func
            return func

        return decorator

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
