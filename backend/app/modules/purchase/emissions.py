from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

settings = get_settings()
logger = get_logger(__name__)


@DataEntryEmissionService.register_formula(EmissionType.purchases__goods_and_services)
@DataEntryEmissionService.register_formula(EmissionType.purchases__scientific_equipment)
@DataEntryEmissionService.register_formula(EmissionType.purchases__it_equipment)
@DataEntryEmissionService.register_formula(
    EmissionType.purchases__consumable_accessories
)
@DataEntryEmissionService.register_formula(
    EmissionType.purchases__biological_chemical_gaseous
)
@DataEntryEmissionService.register_formula(EmissionType.purchases__services)
@DataEntryEmissionService.register_formula(EmissionType.purchases__vehicles)
@DataEntryEmissionService.register_formula(EmissionType.purchases__other)
async def compute_purchase(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for purchases."""
    # Implement actual calculation based on data_entry data
    kg_co2eq = None
    total_spent_amount = data_entry.data.get("total_spent_amount", 0)
    # Default currency is CHF
    # TODO currency handling in issue #402
    # currency = data_entry.data.get("currency", "chf").lower()
    purchase_institutional_code = data_entry.data.get(
        "purchase_institutional_code", None
    )
    if purchase_institutional_code is None:
        logger.warning("purchase_institutional_code is missing in data entry data")
        return {"kg_co2eq": kg_co2eq}
    if not factors or len(factors) == 0:
        return {"kg_co2eq": kg_co2eq}

    # Find factor matching the purchase_institutional_code
    purchase_factors = [
        f
        for f in factors
        if f.classification.get("purchase_institutional_code")
        == purchase_institutional_code
    ]
    if not purchase_factors or len(purchase_factors) == 0:
        logger.warning(
            "No factor found matching purchase_institutional_code: "
            f"{purchase_institutional_code}"
        )
        return {"kg_co2eq": kg_co2eq}
    purchase_factor = purchase_factors[0]
    if total_spent_amount and purchase_factor and purchase_factor.values:
        kg_co2eq = total_spent_amount * purchase_factor.values.get(
            "ef_kg_co2eq_per_currency", 0
        )
    # return intermediary dict with calculation details alway kg_co2eq at least
    return {"kg_co2eq": kg_co2eq}


@DataEntryEmissionService.register_formula(EmissionType.purchases__additional)
async def compute_additional_purchase(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for additional purchases."""
    # Implement actual calculation based on data_entry data
    kg_co2eq = None
    name = data_entry.data.get("name", "")
    if not name:
        logger.warning("name is missing in data entry data for additional purchase")
        return {"kg_co2eq": kg_co2eq}
    annual_consumption = data_entry.data.get("annual_consumption", 0)
    coef_to_kg = data_entry.data.get("coef_to_kg", 0)
    if not factors or len(factors) == 0:
        return {"kg_co2eq": kg_co2eq}

    # Find factor matching the name
    purchase_factors = [f for f in factors if f.classification.get("name") == name]
    if not purchase_factors or len(purchase_factors) == 0:
        logger.warning(f"No factor found matching name: {name}")
        return {"kg_co2eq": kg_co2eq}
    purchase_factor = purchase_factors[0]
    if annual_consumption and coef_to_kg:
        kg_co2eq = (
            annual_consumption
            * coef_to_kg
            * purchase_factor.values.get("ef_kg_co2eq_per_kg", 0)
        )
    # return intermediary dict with calculation details alway kg_co2eq at least
    return {"kg_co2eq": kg_co2eq}
