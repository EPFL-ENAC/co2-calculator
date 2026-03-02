from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

settings = get_settings()
logger = get_logger(__name__)


@DataEntryEmissionService.register_formula(EmissionType.process_emissions__ch4)
@DataEntryEmissionService.register_formula(EmissionType.process_emissions__co2)
@DataEntryEmissionService.register_formula(EmissionType.process_emissions__n2o)
@DataEntryEmissionService.register_formula(EmissionType.process_emissions__refrigerants)
async def compute_process_emissions(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Emissions_CO2eq = Quantity (kg) × GWP_factor"""
    quantity_kg = data_entry.data.get("quantity_kg", 0)
    if not factors:
        return {"kg_co2eq": None}
    factor = factors[0]

    gwp = factor.values.get("gwp_kg_co2eq_per_kg", 0)
    # Defensive check for legacy or corrupted data: quantity must not be negative.
    if quantity_kg < 0:
        return {"kg_co2eq": None}

    kg_co2eq = quantity_kg * gwp
    return {"kg_co2eq": kg_co2eq, "quantity_kg": quantity_kg, "gwp_factor": gwp}
