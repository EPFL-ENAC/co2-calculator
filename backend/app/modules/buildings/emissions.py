from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

settings = get_settings()
logger = get_logger(__name__)


@DataEntryEmissionService.register_formula(EmissionType.buildings__rooms__cooling)
async def compute_building_room_cooling(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute building room energy emissions.

    kWh by category comes from Archibus room data:
    category_kwh = room_surface_square_meter * category_kwh_per_square_meter
    kg_co2eq = sum(category_kwh * ef_kg_co2eq_per_kwh * conversion_factor)
    """
    return await compute_building_category_cooling(self, data_entry, factors, "cooling")


@DataEntryEmissionService.register_formula(EmissionType.buildings__rooms__heating_elec)
async def compute_building_room_heating(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute building room energy emissions.

    kWh by category comes from Archibus room data:
    category_kwh = room_surface_square_meter * category_kwh_per_square_meter
    kg_co2eq = sum(category_kwh * ef_kg_co2eq_per_kwh * conversion_factor)
    """
    return await compute_building_category_cooling(self, data_entry, factors, "heating")


@DataEntryEmissionService.register_formula(EmissionType.buildings__rooms__lighting)
async def compute_building_room_lighting(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute building room energy emissions.

    kWh by category comes from Archibus room data:
    category_kwh = room_surface_square_meter * category_kwh_per_square_meter
    kg_co2eq = sum(category_kwh * ef_kg_co2eq_per_kwh * conversion_factor)
    """
    return await compute_building_category_cooling(
        self, data_entry, factors, "lighting"
    )


@DataEntryEmissionService.register_formula(EmissionType.buildings__rooms__ventilation)
async def compute_building_room_ventilation(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute building room energy emissions.

    kWh by category comes from Archibus room data:
    category_kwh = room_surface_square_meter * category_kwh_per_square_meter
    kg_co2eq = sum(category_kwh * ef_kg_co2eq_per_kwh * conversion_factor)
    """
    return await compute_building_category_cooling(
        self, data_entry, factors, "ventilation"
    )


async def compute_building_category_cooling(
    self,
    data_entry: DataEntry | DataEntryResponse,
    factors: list[Factor],
    category: str,
) -> dict:
    """Compute building room energy emissions.

    kWh by category comes from Archibus room data:
    category_kwh = room_surface_square_meter * category_kwh_per_square_meter
    kg_co2eq = sum(category_kwh * ef_kg_co2eq_per_kwh * conversion_factor)
    category is expected to be one of "heating", "cooling", "ventilation" or "lighting"
    and is used to find the right kwh_per_square_meter and factor subkind.
    """
    surface = data_entry.data.get("room_surface_square_meter")
    if not surface or surface <= 0:
        return {"kg_co2eq": None}
    if not factors:
        return {"kg_co2eq": None}
    kwh_per_m2 = data_entry.data.get(f"{category}_kwh_per_square_meter") or 0

    kwh = kwh_per_m2 * surface

    # construct a map of factors by subkind
    factor_by_category: dict[str, Factor] = {
        str(subkind).lower(): factor
        for factor in factors
        if (subkind := (factor.classification or {}).get("subkind"))
    }

    def _category_kg(category: str, kwh: float) -> float | None:
        factor = factor_by_category.get(category)
        if factor is None:
            return None
        ef = factor.values.get("ef_kg_co2eq_per_kwh")
        if ef is None:
            return None
        conversion_factor = factor.values.get("conversion_factor")
        conversion = (
            conversion_factor
            if isinstance(conversion_factor, (int, float)) and conversion_factor > 0
            else 1.0
        )
        return kwh * ef * conversion

    kg_co2eq = _category_kg(category, kwh)

    return {
        "kg_co2eq": kg_co2eq,
        "kwh": kwh,
    }


@DataEntryEmissionService.register_formula(EmissionType.buildings__combustion)
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
