from typing import Callable, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.emission_type import EmissionTypeEnum
from app.models.factor import Factor
from app.models.location import Location
from app.repositories.data_entry_emission_repo import (
    DataEntryEmissionRepository,
)
from app.repositories.factor_repo import FactorRepository
from app.schemas.data_entry import DataEntryResponse
from app.services.factor_service import FactorService
from app.utils.distance_geography import (
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
)

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
        # TODO: Make generic for all types!!!
        # for cloud it's this key
        if data_entry.data_entry_type == DataEntryTypeEnum.external_clouds:
            emission_type = EmissionTypeEnum[
                data_entry.data.get("sub_kind") or "calcul"
            ]
        elif data_entry.data_entry_type == DataEntryTypeEnum.external_ai:
            emission_type = EmissionTypeEnum.ai_provider
        elif data_entry.data_entry_type == DataEntryTypeEnum.trips:
            # Travel is handled specially - calculate emissions directly
            # TODO: change enum to match transport_mode
            transport_mode = data_entry.data.get("transport_mode", "flight")
            emission_type = EmissionTypeEnum[transport_mode]
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

        if data_entry.data_entry_type == DataEntryTypeEnum.trips:
            primary_factor, distance_km = await self._resolve_trip_factor(data_entry)
            if not primary_factor:
                logger.warning(
                    f"Could not resolve factor for trip entry {data_entry.id}"
                )
                return None
            primary_factor_id = primary_factor.id
            data_entry.data["distance_km"] = distance_km
            factors = [primary_factor]
        else:
            # Other types: factor already resolved by handler
            primary_factor_id = data_entry.data.get("primary_factor_id")
            if not primary_factor_id:
                return None

            factor_service = FactorService(self.session)
            primary_factor = await factor_service.get(primary_factor_id)
            if not primary_factor:
                return None
            factors = [primary_factor]

            # Equipment types need electricity factor too
            if (
                data_entry.data_entry_type == DataEntryTypeEnum.scientific
                or data_entry.data_entry_type == DataEntryTypeEnum.it
                or data_entry.data_entry_type == DataEntryTypeEnum.other
            ):
                electricity_factor = await factor_service.get_electricity_factor()
                if electricity_factor:
                    factors.append(electricity_factor)

        # returns the factors used
        emissions_value = self._calculate_emissions(data_entry, factors=factors)
        if data_entry.id is None:
            logger.error("DataEntry must have an ID before creating emissions.")
            return None
        if emissions_value.get("kg_co2eq") is None:
            logger.error(
                "No emissions calculated for DataEntry ID "
                f"{data_entry.id}. Skipping emission record creation"
                f"{primary_factor}"
            )
            return None
        subcategory = None  # TODO: should be an enum somwhere
        if data_entry.data_entry_type == DataEntryTypeEnum.trips:
            subcategory = data_entry.data.get("transport_mode", "flight")
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

    async def _resolve_trip_factor(
        self, data_entry: DataEntryResponse | DataEntry
    ) -> tuple[Optional[Factor], Optional[float]]:
        """
        Resolve factor and calculate distance for trips.
        This is where 'Distance * Factor' calculation happens per the sequence.

        Returns:
            tuple of (factor, distance_km) or (None, None) if resolution fails
        """
        origin_id = data_entry.data.get("origin_location_id")
        dest_id = data_entry.data.get("destination_location_id")
        transport_mode = data_entry.data.get("transport_mode", "flight")

        if not origin_id or not dest_id:
            logger.warning("Missing origin or destination location for trip")
            return None, None

        origin_loc = await self.session.get(Location, origin_id)
        dest_loc = await self.session.get(Location, dest_id)

        if not origin_loc or not dest_loc:
            logger.warning(
                f"Could not find locations: origin={origin_id}, dest={dest_id}"
            )
            return None, None

        factor_repo = FactorRepository(self.session)

        if transport_mode == "flight":
            distance_km = calculate_plane_distance(origin_loc, dest_loc)
            category = get_haul_category(distance_km)
            factor = await factor_repo.get_factor(
                DataEntryTypeEnum.trips, kind="flight", category=category
            )
            return factor, distance_km

        elif transport_mode == "train":
            distance_km = calculate_train_distance(origin_loc, dest_loc)
            dest_country = dest_loc.countrycode or "RoW"
            factor = await factor_repo.get_factor(
                DataEntryTypeEnum.trips,
                fallbacks={"countrycode": "RoW"},
                kind="train",
                countrycode=dest_country,
            )
            return factor, distance_km

        else:
            logger.warning(f"Unknown transport_mode: {transport_mode}")
            return None, None

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
    ) -> dict[str, float]:
        """Get aggregated emission statistics for a carbon report module."""
        stats = await self.repo.get_stats(
            carbon_report_module_id,
            aggregate_by,
            aggregate_field,
        )
        return stats

    # Dict of dataEntryTypeEnum , func to calculation formulas
    FORMULAS: dict[DataEntryTypeEnum, Callable] = {}

    # create a decorator to register formulas
    @classmethod
    def register_formula(cls, name: DataEntryTypeEnum):
        def decorator(func):
            cls.FORMULAS[name] = func
            return func

        return decorator

    def _calculate_emissions(
        self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
    ) -> dict:
        """Placeholder method for emissions calculation logic."""
        # Implement actual calculation based on data_entry data
        if data_entry.data_entry_type is None:
            raise ValueError("Data entry type is required for emissions calculation")
        formula_func = self.FORMULAS.get(data_entry.data_entry_type)
        if formula_func:
            return formula_func(self, data_entry, factors)
        else:
            raise ValueError(f"No formula registered for: {data_entry.data_entry_type}")


# Register formulas for different DataEntryTypeEnum
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.external_clouds)
def compute_external_clouds(
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
def compute_external_ai(
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
def compute_scientific_it_other(
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


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.trips)
def compute_trips(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for professional travel (trips)."""
    transport_mode = data_entry.data.get("transport_mode", "flight")
    cabin_class = data_entry.data.get("cabin_class")
    number_of_trips = data_entry.data.get("number_of_trips", 1)
    origin_location_id = data_entry.data.get("origin_location_id")
    destination_location_id = data_entry.data.get("destination_location_id")
    distance_km = data_entry.data.get("distance_km")

    response = {
        "kg_co2eq": None,
        "distance_km": distance_km,
        "transport_mode": transport_mode,
        "cabin_class": cabin_class,
        "number_of_trips": number_of_trips,
        "origin_location_id": origin_location_id,
        "destination_location_id": destination_location_id,
    }

    if not factors or len(factors) == 0:
        logger.warning("No factors provided for trips emission calculation")
        return response

    factor = factors[0]

    if transport_mode == "flight":
        result = compute_travel_plane(data_entry, factor)
    elif transport_mode == "train":
        result = compute_travel_train(data_entry, factor)
    else:
        logger.warning(f"Unknown transport_mode: {transport_mode}")
        return response

    response["kg_co2eq"] = result.get("kg_co2eq")
    return response


def compute_travel_plane(
    data_entry: DataEntry | DataEntryResponse,
    factor: Factor,
) -> dict:
    """Compute emissions for plane travel."""
    distance_km = data_entry.data.get("distance_km")
    number_of_trips = data_entry.data.get("number_of_trips", 1)

    if not distance_km:
        logger.warning("Missing distance_km for flight emission calculation")
        return {"kg_co2eq": None}

    impact_score = factor.values.get("impact_score", 0)
    rfi_adjustment = factor.values.get("rfi_adjustment", 1)
    kg_co2eq = distance_km * impact_score * rfi_adjustment * number_of_trips

    logger.debug(
        f"Flight: {distance_km}km × {impact_score} × {rfi_adjustment} "
        f"× {number_of_trips} = {kg_co2eq:.2f} kg CO2eq"
    )

    return {"kg_co2eq": round(kg_co2eq, 2)}


def compute_travel_train(
    data_entry: DataEntry | DataEntryResponse,
    factor: Factor,
) -> dict:
    """Compute emissions for train travel."""
    distance_km = data_entry.data.get("distance_km")
    number_of_trips = data_entry.data.get("number_of_trips", 1)

    if not distance_km:
        logger.warning("Missing distance_km for train emission calculation")
        return {"kg_co2eq": None}

    impact_score = factor.values.get("impact_score", 0)
    kg_co2eq = distance_km * impact_score * number_of_trips

    logger.debug(
        f"Train: {distance_km}km × {impact_score} "
        f"× {number_of_trips} = {kg_co2eq:.2f} kg CO2eq"
    )

    return {"kg_co2eq": round(kg_co2eq, 2)}
