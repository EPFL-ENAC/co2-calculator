from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
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


class ProfessionalTravelPlaneHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = None
    kg_co2eq: Optional[float] = None


class ProfessionalTravelTrainHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = None
    kg_co2eq: Optional[float] = None


class ProfessionalTravelPlaneHandlerCreate(DepartureDateMixin, DataEntryCreate):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: int = 1


class ProfessionalTravelTrainHandlerCreate(DepartureDateMixin, DataEntryCreate):
    traveler_name: str
    traveler_id: Optional[int] = None
    origin_location_id: int
    destination_location_id: int
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: int = 1


class ProfessionalTravelPlaneHandlerUpdate(DataEntryUpdate):
    traveler_name: Optional[str] = None
    traveler_id: Optional[int] = None
    origin_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None


class ProfessionalTravelTrainHandlerUpdate(DataEntryUpdate):
    traveler_name: Optional[str] = None
    traveler_id: Optional[int] = None
    origin_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None


class ProfessionalTravelBaseModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.professional_travel
    data_entry_type: DataEntryTypeEnum
    create_dto: type[DataEntryCreate]
    update_dto: type[DataEntryUpdate]
    response_dto: type[DataEntryResponseGen]

    kind_field = None
    subkind_field = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "traveler_name": DataEntry.data["traveler_name"].as_string(),
        "departure_date": DataEntry.data["departure_date"].as_string(),
        "cabin_class": DataEntry.data["cabin_class"].as_string(),
        "number_of_trips": DataEntry.data["number_of_trips"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    def to_response(self, data_entry: DataEntry) -> DataEntryResponseGen:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)


class ProfessionalTravelPlaneModuleHandler(ProfessionalTravelBaseModuleHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.plane
    create_dto = ProfessionalTravelPlaneHandlerCreate
    update_dto = ProfessionalTravelPlaneHandlerUpdate
    response_dto = ProfessionalTravelPlaneHandlerResponse


class ProfessionalTravelTrainModuleHandler(ProfessionalTravelBaseModuleHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.train
    create_dto = ProfessionalTravelTrainHandlerCreate
    update_dto = ProfessionalTravelTrainHandlerUpdate
    response_dto = ProfessionalTravelTrainHandlerResponse
