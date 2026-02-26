from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.location import TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

logger = get_logger(__name__)


class DepartureDateMixin(BaseModel):
    """Mixin for parsing departure_date from various formats."""

    @field_validator("departure_date", mode="before", check_fields=False)
    @classmethod
    def parse_departure_date(cls, v: Any) -> Optional[date]:
        """Parse departure_date from various formats (date, datetime, string)."""
        if v is None:
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            if not v.strip():
                return None
            normalized = v.replace("/", "-")
            try:
                return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date()
            except ValueError:
                return date.fromisoformat(normalized)
        return v


class ProfessionalTravelHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    transport_mode: TransportModeEnum
    cabin_class: Optional[str] = None  # eco, business, first, class_1, class_2
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    is_round_trip: bool = False
    trip_direction: Optional[str] = None  # "outbound" or "return"
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = None
    kg_co2eq: Optional[float] = None


class ProfessionalTravelHandlerCreate(DepartureDateMixin, DataEntryCreate):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    transport_mode: TransportModeEnum
    cabin_class: Optional[str] = None  # eco, business, first, class_1, class_2
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    is_round_trip: bool = False
    trip_direction: Optional[str] = None  # "outbound" or "return"


class ProfessionalTravelHandlerUpdate(DataEntryUpdate):
    traveler_name: Optional[str] = None
    traveler_id: Optional[int] = None
    origin_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None
    transport_mode: Optional[TransportModeEnum] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None


class ProfessionalTravelModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.professional_travel
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.trips
    create_dto = ProfessionalTravelHandlerCreate
    update_dto = ProfessionalTravelHandlerUpdate
    response_dto = ProfessionalTravelHandlerResponse

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "traveler_name": DataEntry.data["traveler_name"].as_string(),
        "departure_date": DataEntry.data["departure_date"].as_string(),
        "transport_mode": DataEntry.data["transport_mode"].as_string(),
        "cabin_class": DataEntry.data["cabin_class"].as_string(),
        "number_of_trips": DataEntry.data["number_of_trips"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    # async def resolve_primary_factor_id(
    #     self,
    #     payload: dict,
    #     data_entry_type_id: DataEntryTypeEnum,
    #     db: AsyncSession,
    #     existing_data: Optional[dict] = None,
    # ) -> dict:
    #     """
    #     Resolve factor ID if kind/or subkind change
    #     Sets primary_factor_id

    #     distance is computed in emission_service
    #     """
    # # Merge payload with existing data
    # origin_id = payload.get("origin_location_id")
    # dest_id = payload.get("destination_location_id")
    # transport_mode = payload.get("transport_mode")

    # if existing_data:
    #     if origin_id is None:
    #         origin_id = existing_data.get("origin_location_id")
    #     if dest_id is None:
    #         dest_id = existing_data.get("destination_location_id")
    #     if transport_mode is None:
    #         transport_mode = existing_data.get("transport_mode")

    # if not origin_id or not dest_id:
    #     logger.warning("Missing origin or destination location for trip")
    #     return payload

    # if not transport_mode or transport_mode not in
    #   (TransportModeEnum.plane, TransportModeEnum.train):
    #     logger.warning(f"Unknown transport_mode: {transport_mode}")
    #     return payload

    # OriginLoc = aliased(Location, name="origin")
    # DestLoc = aliased(Location, name="dest")

    # stmt = (
    #     sa_select(OriginLoc, DestLoc, Factor)
    #     .select_from(OriginLoc)
    #     .join(DestLoc, col(DestLoc.id) == dest_id)
    #     .outerjoin(
    #         Factor,
    #         and_(
    #             col(Factor.data_entry_type_id) == DataEntryTypeEnum.trips.value,
    #             Factor.classification["kind"].as_string() == transport_mode,
    #         ),
    #     )
    #     .where(col(OriginLoc.id) == origin_id)
    # )

    # result = await db.execute(stmt)
    # rows = result.all()

    # if not rows:
    #     logger.warning("Missing origin or destination location for trip")
    #     return payload

    # origin_loc, dest_loc = rows[0][0], rows[0][1]
    # factors = [row[2] for row in rows if row[2] is not None]

    # payload["origin"] = origin_loc.name
    # payload["destination"] = dest_loc.name

    # if transport_mode == "plane":
    #     distance_km, factor = resolve_flight_factor(origin_loc, dest_loc, factors)
    # else:  # train
    #     distance_km, factor = resolve_train_factor(origin_loc, dest_loc, factors)

    # payload["distance_km"] = distance_km
    # payload["primary_factor_id"] = factor.id if factor else None

    # return payload

    def to_response(self, data_entry: DataEntry) -> ProfessionalTravelHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> ProfessionalTravelHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ProfessionalTravelHandlerUpdate:
        return self.update_dto.model_validate(payload)
