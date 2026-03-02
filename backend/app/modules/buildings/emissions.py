from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

settings = get_settings()
logger = get_logger(__name__)


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.building)
async def compute_building_room(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute building room energy emissions.

    kWh by category comes from Archibus room data:
    category_kwh = room_surface_square_meter * category_kwh_per_square_meter
    kg_co2eq = sum(category_kwh * ef_kg_co2eq_per_kwh * conversion_factor)
    """
    surface = data_entry.data.get("room_surface_square_meter")
    if not surface or surface <= 0:
        return {"kg_co2eq": None}
    if not factors:
        return {"kg_co2eq": None}
    heating_kwh_per_m2 = data_entry.data.get("heating_kwh_per_square_meter") or 0
    cooling_kwh_per_m2 = data_entry.data.get("cooling_kwh_per_square_meter") or 0
    ventilation_kwh_per_m2 = (
        data_entry.data.get("ventilation_kwh_per_square_meter") or 0
    )
    lighting_kwh_per_m2 = data_entry.data.get("lighting_kwh_per_square_meter") or 0

    heating_kwh = heating_kwh_per_m2 * surface
    cooling_kwh = cooling_kwh_per_m2 * surface
    ventilation_kwh = ventilation_kwh_per_m2 * surface
    lighting_kwh = lighting_kwh_per_m2 * surface

    factor_by_category: dict[str, Factor] = {}
    for factor in factors:
        subkind = (factor.classification or {}).get("subkind")
        if subkind:
            factor_by_category[str(subkind).lower()] = factor
    if not factor_by_category:
        return {"kg_co2eq": None}

    def _category_kg(category: str, kwh: float) -> float:
        factor = factor_by_category.get(category)
        if factor is None:
            return 0.0
        ef = factor.values.get("ef_kg_co2eq_per_kwh")
        if ef is None:
            return 0.0
        conversion_factor = factor.values.get("conversion_factor")
        conversion = (
            conversion_factor
            if isinstance(conversion_factor, (int, float)) and conversion_factor > 0
            else 1.0
        )
        return kwh * ef * conversion

    heating_kg_co2eq = _category_kg("heating", heating_kwh)
    cooling_kg_co2eq = _category_kg("cooling", cooling_kwh)
    ventilation_kg_co2eq = _category_kg("ventilation", ventilation_kwh)
    lighting_kg_co2eq = _category_kg("lighting", lighting_kwh)
    kg_co2eq = (
        heating_kg_co2eq + cooling_kg_co2eq + ventilation_kg_co2eq + lighting_kg_co2eq
    )

    return {
        "kg_co2eq": kg_co2eq,
        "heating_kwh": heating_kwh,
        "cooling_kwh": cooling_kwh,
        "ventilation_kwh": ventilation_kwh,
        "lighting_kwh": lighting_kwh,
        "heating_kg_co2eq": heating_kg_co2eq,
        "cooling_kg_co2eq": cooling_kg_co2eq,
        "ventilation_kg_co2eq": ventilation_kg_co2eq,
        "lighting_kg_co2eq": lighting_kg_co2eq,
    }


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.energy_combustion)
async def compute_energy_combustion(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute energy combustion emissions.

    kg_co2eq = quantity * factor kg_co2eq_per_unit
    """
    quantity = data_entry.data.get("quantity")
    if not quantity or quantity <= 0:
        return {"kg_co2eq": None}
    if not factors:
        return {"kg_co2eq": None}

    factor = factors[0]
    kgco2_per_unit = factor.values.get("kg_co2eq_per_unit", 0)
    kg_co2eq = quantity * kgco2_per_unit

    return {
        "kg_co2eq": kg_co2eq,
        "quantity": quantity,
        "unit": factor.values.get("unit", ""),
        "factor_kg_co2eq_per_unit": kgco2_per_unit,
    }
