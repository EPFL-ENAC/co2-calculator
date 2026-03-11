from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ValidationInfo, field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
    FactorQuery,
)
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)
from app.services.location_service import LocationService
from app.utils.distance_geography import (
    _determine_train_countrycode,
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
)

logger = get_logger(__name__)


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


class TrainCabinClassValidationMixin:
    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: Optional[str]) -> Optional[str]:
        valid_classes = ["first", "second"]
        if v is not None and v.lower() not in valid_classes:
            raise ValueError(
                f"Invalid cabin class '{v}', must be one of {valid_classes}"
            )
        return v.lower() if v else None


class PlaneCabinClassValidationMixin:
    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: Optional[str]) -> Optional[str]:
        valid_classes = ["first", "business", "economy"]
        if v is not None and v.lower() not in valid_classes:
            raise ValueError(
                f"Invalid cabin class '{v}', must be one of {valid_classes}"
            )
        return v.lower() if v else None


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
    origin_iata: str  ## IATA code
    destination_iata: str  ## IATA code
    user_institutional_id: str
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    cabin_class: str
    note: Optional[str] = None


class ProfessionalTravelTrainHandlerCreate(DepartureDateMixin, DataEntryCreate):
    user_institutional_id: str
    origin_name: str
    destination_name: str
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    cabin_class: str
    note: Optional[str] = None


class ProfessionalTravelPlaneHandlerUpdate(DataEntryUpdate):
    # traveler_name: Optional[str] = None
    # traveler_id: Optional[int] = None
    origin_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None


class ProfessionalTravelTrainHandlerUpdate(DataEntryUpdate):
    # traveler_name: Optional[str] = None
    # traveler_id: Optional[int] = None
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

    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None
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

    kind_field: str = "category"

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """Compute flight distance and haul category
        from origin/destination airports."""
        origin_iata = data_entry.data.get("origin_iata")
        destination_iata = data_entry.data.get("destination_iata")
        number_of_trips = data_entry.data.get("number_of_trips", 1)
        if origin_iata is None or destination_iata is None:
            return {}

        loc_service = LocationService(session)
        origin = await loc_service.get_location_by_iata(origin_iata)
        dest = await loc_service.get_location_by_iata(destination_iata)
        if not origin or not dest:
            return {}
        distance_one_trip_km = calculate_plane_distance(
            origin_airport=origin,
            dest_airport=dest,
        )
        if distance_one_trip_km is None:
            return {}
        haul_category = get_haul_category(distance_one_trip_km)
        distance_km = distance_one_trip_km * number_of_trips
        return {
            "distance_one_trip_km": distance_one_trip_km,
            "haul_category": haul_category,
            "distance_km": distance_km,
        }

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        # cabin_class = data_entry.data.get("cabin_class")
        haul_category = ctx.get("haul_category")
        # context: dict = {}
        if haul_category is None:
            logger.warning(
                f"Haul category could not be determined for data entry {data_entry.id}"
            )
            haul_category = "unknown"
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.plane,
                    kind=haul_category,
                    subkind=None,
                    context={},
                ),
                formula_key="ef_kg_co2eq_per_km",
                quantity_key="distance_km",
                multiplier_key="rfi_adjustment",
                multiplier_default=1.0,
            )
        ]


class ProfessionalTravelTrainModuleHandler(ProfessionalTravelBaseModuleHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.train
    create_dto = ProfessionalTravelTrainHandlerCreate
    update_dto = ProfessionalTravelTrainHandlerUpdate
    response_dto = ProfessionalTravelTrainHandlerResponse

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """Compute train distance and determine relevant country code."""
        origin_name = data_entry.data.get("origin_name")
        destination_name = data_entry.data.get("destination_name")
        number_of_trips = data_entry.data.get("number_of_trips", 1)
        if origin_name is None or destination_name is None:
            return {}

        loc_service = LocationService(session)
        origin = await loc_service.get_location_by_name(origin_name)
        dest = await loc_service.get_location_by_name(destination_name)
        if origin is None or dest is None:
            return {}
        distance_one_trip_km = calculate_train_distance(
            origin_station=origin,
            dest_station=dest,
        )
        if distance_one_trip_km is None:
            return {}
        distance_km = distance_one_trip_km * number_of_trips

        country_code = _determine_train_countrycode(origin, dest)
        return {
            "distance_km": distance_km,
            "distance_one_trip_km": distance_one_trip_km,
            "country_code": country_code,
        }

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:
        country_code = ctx.get("country_code") or None
        # todo check that fallbacks works! it was not the case!

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.train,
                    # Train factors are keyed by country_code in classification.
                    # Fall back to RoW if the exact country is not found.
                    kind=None,
                    subkind=None,
                    context={"country_code": country_code},
                    fallbacks={"country_code": "RoW"},
                ),
                formula_key="ef_kg_co2eq_per_km",
                quantity_key="distance_km",
            )
        ]


class TravelPlaneBase:
    category: str
    ef_kg_co2eq_per_km: float
    rfi_adjustment: float
    # todo adjustment instead of adjustement
    class_adjustement: float
    min_distance: float
    max_distance: float


class _TravelPlaneBaseValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_km",
        "rfi_adjustment",
        "class_adjustement",
        "min_distance",
        "max_distance",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid_categories = [
            "very_short_haul",
            "short_haul",
            "medium_haul",
            "long_haul",
        ]
        if not v:
            raise ValueError("Category is required")
        if v not in valid_categories:
            raise ValueError("Invalid category")
        return v


class TravelPlaneFactorResponse(
    FactorResponseGen, TravelPlaneBase, _TravelPlaneBaseValidationMixin
):
    pass


class TravelPlaneFactorCreate(
    FactorCreate, TravelPlaneBase, _TravelPlaneBaseValidationMixin
):
    pass


class TravelPlaneFactorUpdate(
    FactorUpdate, TravelPlaneBase, _TravelPlaneBaseValidationMixin
):
    pass


class TravelPlaneFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.plane
    registration_keys = [DataEntryTypeEnum.plane]
    emission_type: EmissionType = EmissionType.professional_travel__plane

    classification_fields: list[str] = ["category"]
    value_fields: list[str] = [
        "ef_kg_co2eq_per_km",
        "class_adjustement",
        "rfi_adjustment",
        "min_distance",
        "max_distance",
    ]

    create_dto = TravelPlaneFactorCreate
    update_dto = TravelPlaneFactorUpdate
    response_dto = TravelPlaneFactorResponse


class TravelTrainBase:
    country_code: str
    ef_kg_co2eq_per_km: float


class _TravelTrainBaseValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_km",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("country_code", mode="after")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        # in ISO 3166-1 alpha-2 format or use RoW for rest of the world
        # for now we check two letter format but we don't validate against
        # a list of actual country codes
        if not v:
            raise ValueError("Country code is required")
        if v != "RoW" and (len(v) != 2 or not v.isalpha()):
            raise ValueError(
                "Invalid country code, must be ISO 3166-1 alpha-2 or 'RoW'"
            )
        return v


class TravelTrainFactorResponse(
    FactorResponseGen, TravelTrainBase, _TravelTrainBaseValidationMixin
):
    pass


class TravelTrainFactorCreate(
    FactorCreate, TravelTrainBase, _TravelTrainBaseValidationMixin
):
    pass


class TravelTrainFactorUpdate(
    FactorUpdate, TravelTrainBase, _TravelTrainBaseValidationMixin
):
    pass


class TravelTrainFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.train
    emission_type: EmissionType = EmissionType.professional_travel__train

    registration_keys = [DataEntryTypeEnum.train]

    classification_fields: list[str] = ["country_code"]
    value_fields: list[str] = ["ef_kg_co2eq_per_km"]

    create_dto = TravelTrainFactorCreate
    update_dto = TravelTrainFactorUpdate
    response_dto = TravelTrainFactorResponse
