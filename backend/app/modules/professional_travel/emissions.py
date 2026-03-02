from sqlalchemy.orm import aliased
from sqlmodel import and_, col, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.factor import Factor
from app.models.location import (
    PlaneLocation,
    TrainLocation,
    TransportModeEnum,
)
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.utils.distance_geography import (
    resolve_flight_factor,
    resolve_train_factor,
)

settings = get_settings()
logger = get_logger(__name__)


@DataEntryEmissionService.register_formula(DataEntryTypeEnum.plane)
@DataEntryEmissionService.register_formula(DataEntryTypeEnum.train)
async def compute_trips(
    self, data_entry: DataEntry | DataEntryResponse, factors: list[Factor]
) -> dict:
    """Compute emissions for professional travel (trips)."""
    selected_type = DataEntryTypeEnum(data_entry.data_entry_type)
    mode = (
        TransportModeEnum.plane
        if selected_type == DataEntryTypeEnum.plane
        else TransportModeEnum.train
    )
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

    location_model: type[PlaneLocation] | type[TrainLocation] = (
        PlaneLocation if selected_type == DataEntryTypeEnum.plane else TrainLocation
    )
    OriginLoc = aliased(location_model, name="origin")
    DestLoc = aliased(location_model, name="dest")

    stmt = (
        select(OriginLoc, DestLoc, Factor)
        .select_from(OriginLoc)
        .join(DestLoc, col(DestLoc.id) == dest_id)
        .outerjoin(
            Factor,
            and_(
                col(Factor.data_entry_type_id) == selected_type.value,
                Factor.classification["kind"].as_string() == mode.value,
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

    if mode == TransportModeEnum.plane:
        distance_km, matched_factor = resolve_flight_factor(
            origin_loc, dest_loc, factors
        )
        if not distance_km or not matched_factor:
            logger.warning("Could not resolve flight distance or factor")
            return response
        distance_km = distance_km * number_of_trips
        factor_values = matched_factor.values or {}
        result = compute_travel_plane(distance_km, factor_values)
    elif mode == TransportModeEnum.train:
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
        logger.warning(f"Unknown mode: {mode}")
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
    impact_score = factor_values.get("impact_score", 0)
    rfi_adjustment = factor_values.get("rfi_adjustment", 1)
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
    impact_score = factor_values.get("impact_score", 0)
    kg_co2eq = distance_km * impact_score

    logger.debug(f"Train: {distance_km}km × {impact_score} = {kg_co2eq:.2f} kg CO2eq")

    return {"kg_co2eq": kg_co2eq}
