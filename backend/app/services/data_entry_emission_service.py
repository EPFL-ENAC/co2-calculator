from typing import Callable

from sqlalchemy.orm import aliased
from sqlmodel import and_, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType, get_scope
from app.models.factor import Factor
from app.models.location import Location
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.services.factor_service import FactorService
from app.utils.data_entry_emission_type_map import resolve_emission_types
from app.utils.distance_geography import resolve_flight_factor, resolve_train_factor

settings = get_settings()
logger = get_logger(__name__)


class DataEntryEmissionService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryEmissionRepository(session)

    async def prepare_create(
        self, data_entry: DataEntryResponse | DataEntry
    ) -> list[DataEntryEmission]:
        """Prepare emissions for a data entry, if applicable.

        Returns a list of emissions (one per emission type).
        For member/student types, multiple rows are produced (one per emission type).
        For other types, typically a single row is produced.
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

        # returns the factors used
        emissions_value = await self._calculate_emissions(data_entry, factors=factors)
        if data_entry.id is None:
            logger.error("DataEntry must have an ID before creating emissions.")
            return []
        if emissions_value.get("kg_co2eq") is None:
            logger.error(
                "No emissions calculated for DataEntry ID "
                f"{data_entry.id}. Skipping emission record creation"
                f" (factor_id={primary_factor_id})"
            )
            return []

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
        return [
            DataEntryEmission(
                data_entry_id=data_entry.id,
                emission_type_id=emission_type.value,
                primary_factor_id=primary_factor_id,
                scope=get_scope(emission_type),
                kg_co2eq=emissions_value.get("kg_co2eq"),
                meta={**emissions_value},
            )
            for emission_type in emission_types
        ]

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
    FORMULAS: dict[DataEntryTypeEnum, Callable] = {}

    # create a decorator to register formulas
    @classmethod
    def register_formula(cls, name: DataEntryTypeEnum):
        def decorator(func):
            cls.FORMULAS[name] = func
            return func

        return decorator

    async def _prepare_headcount_emissions(
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


# Register formulas for different DataEntryTypeEnum
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


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.scientific)
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.it)
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.other)
async def compute_scientific_it_other(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for scientific, it, other."""
    # Implement actual calculation based on data_entry data
    kg_co2eq = None
    response = {"kg_co2eq": kg_co2eq}
    if not factors or len(factors) == 0:
        return response

    factor = factors[0]
    active_usage_hours = data_entry.data.get("active_usage_hours", None)
    if active_usage_hours is None:
        logger.warning("active_usage_hours is missing in data entry data")
        return response
    passive_usage_hours = data_entry.data.get("passive_usage_hours", None)
    if passive_usage_hours is None:
        logger.warning("passive_usage_hours is missing in data entry data")
        return response

    active_power_w = factor.values.get("active_power_w", None)
    if active_power_w is None:
        logger.warning("active_power_w is missing in factor values")
        return response
    standby_power_w = factor.values.get("standby_power_w", None)
    if standby_power_w is None:
        logger.warning("standby_power_w is missing in factor values")
        return response
    # Calculate weekly energy consumption in Watt-hours
    weekly_wh = (active_usage_hours * active_power_w) + (
        passive_usage_hours * standby_power_w
    )
    # Convert to annual kWh: (Wh/week * 52 weeks) / 1000
    annual_kwh = (weekly_wh * settings.WEEKS_PER_YEAR) / 1000

    emission_electric_factor = factors[1].values.get("kgco2eq_per_kwh", None)
    if emission_electric_factor is None:
        raise ValueError("factor_kgco2_per_kwh is required for emissions calculation")
    # Calculate CO2 emissions
    kg_co2eq = annual_kwh * emission_electric_factor

    logger.debug(
        f"CO2 calculation: {active_usage_hours}hrs*{active_power_w}W + "
        f"{passive_usage_hours}hrs*{standby_power_w}W = {annual_kwh:.2f} kWh/year * "
        f"{emission_electric_factor} = {kg_co2eq:.2f} kgCO2eq"
    )

    return {"kg_co2eq": kg_co2eq, "weekly_wh": weekly_wh, "annual_kwh": annual_kwh}


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.plane)
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.train)
async def compute_travel(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for professional travel (plane/train)."""
    selected_type = DataEntryTypeEnum(data_entry.data_entry_type)
    cabin_class = data_entry.data.get("cabin_class")
    number_of_trips = data_entry.data.get("number_of_trips", 1)
    distance_km = None

    origin_id = data_entry.data.get("origin_location_id")
    dest_id = data_entry.data.get("destination_location_id")

    ## define response

    response = {
        "kg_co2eq": None,
        "distance_km": distance_km,
        "cabin_class": cabin_class,
        "number_of_trips": number_of_trips,
        "origin_location_id": data_entry.data.get("origin_location_id"),
        "destination_location_id": data_entry.data.get("destination_location_id"),
    }

    if not origin_id or not dest_id:
        logger.warning("Missing origin or destination location for trip")
        return response

    OriginLoc = aliased(Location, name="origin")
    DestLoc = aliased(Location, name="dest")

    stmt = (
        select(OriginLoc, DestLoc, Factor)
        .select_from(OriginLoc)
        .join(DestLoc, col(DestLoc.id) == dest_id)
        .outerjoin(
            Factor,
            and_(
                col(Factor.data_entry_type_id) == selected_type.value,
            ),
        )
        .where(col(OriginLoc.id) == origin_id)
    )

    result = await self.session.execute(stmt)
    rows = result.all()

    if not rows:
        logger.warning("Missing origin or destination location for trip")
        return response

    origin_loc, dest_loc = rows[0][0], rows[0][1]
    factors = [row[2] for row in rows if row[2] is not None]

    if not factors:
        logger.warning("No factor provided for trip emission calculation")
        return response

    if selected_type == DataEntryTypeEnum.plane:
        distance_km, matched_factor = resolve_flight_factor(
            origin_loc, dest_loc, factors
        )
        if not distance_km or not matched_factor:
            logger.warning("Could not resolve flight distance or factor")
            return response
        distance_km = distance_km * number_of_trips
        factor_values = matched_factor.values or {}
        result = compute_travel_plane(distance_km, factor_values)
    elif selected_type == DataEntryTypeEnum.train:
        distance_km, matched_factor = resolve_train_factor(
            origin_loc, dest_loc, factors
        )
        if not distance_km or not matched_factor:
            logger.warning("Could not resolve train distance or factor")
            return response
        distance_km = distance_km * number_of_trips
        factor_values = matched_factor.values or {}
        result = compute_travel_train(distance_km, factor_values)
    else:
        logger.warning("Unknown travel data_entry_type: %s", selected_type)
        return response

    response["distance_km"] = distance_km
    response["kg_co2eq"] = result.get("kg_co2eq")
    return response


def compute_travel_plane(
    distance_km: float,
    factor_values: dict,
) -> dict:
    """Compute emissions for plane travel.

    Args:
        distance_km: Total distance.
        factor_values: Factor values containing impact_score and rfi_adjustment.
    """
    impact_score = factor_values.get("ef_kg_co2eq_per_km", 0)
    rfi_adjustment = factor_values.get("rfi_adjustement", 1)
    kg_co2eq = distance_km * impact_score * rfi_adjustment

    logger.debug(
        f"Flight: {distance_km}km × {impact_score} × {rfi_adjustment} "
        f"= {kg_co2eq:.2f} kg CO2eq"
    )

    return {"kg_co2eq": kg_co2eq}


def compute_travel_train(
    distance_km: float,
    factor_values: dict,
) -> dict:
    """Compute emissions for train travel.

    Args:
        distance_km: Total distance.
        factor_values: Factor values containing impact_score.
    """
    impact_score = factor_values.get("ef_kg_co2eq_per_km", 0)
    kg_co2eq = distance_km * impact_score

    logger.debug(f"Train: {distance_km}km × {impact_score} = {kg_co2eq:.2f} kg CO2eq")

    return {"kg_co2eq": kg_co2eq}


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.process_emissions)
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
