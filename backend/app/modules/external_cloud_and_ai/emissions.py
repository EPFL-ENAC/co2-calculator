from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

settings = get_settings()
logger = get_logger(__name__)


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.external_clouds)
async def compute_external_clouds(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for external clouds."""

    kg_co2eq = None
    # e.g {"electricity_mix_intensity_kgco2_per_eur": 0.1,
    # "cloud_provider_adjustment": 0.2, "service_type_adjustment": 0.2
    #  "factor_kgco2_per_eur": 0.144}
    total_spending_eur = data_entry.data.get("spending", 0)
    if not factors or len(factors) == 0:
        return {"kg_co2eq": kg_co2eq}
    factor = factors[0]
    if total_spending_eur is not None and factor.values is not None:
        kg_co2eq = factor.values.get("factor_kgco2_per_eur", 0) * total_spending_eur
    return {"kg_co2eq": kg_co2eq}


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.external_ai)
async def compute_external_ai(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for external AI."""
    # Implement actual calculation based on data_entry data
    kg_co2eq = None
    frequency = data_entry.data.get("frequency_use_per_day", 0)
    number_of_users = data_entry.data.get("user_count", 0)
    if not factors or len(factors) == 0:
        return {"kg_co2eq": kg_co2eq}

    factor = factors[0]
    if frequency and number_of_users and factor.values:
        kg_co2eq = (
            (frequency * 5 * 46 * number_of_users)
            * factor.values.get("factor_gCO2eq", 0)
        ) / 1000
    # return intermediary dict with calculation details alway kg_co2eq at least
    return {"kg_co2eq": kg_co2eq}
