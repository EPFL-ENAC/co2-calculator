"""Factor schemas for API requests, responses, and CSV validation."""

from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor

FACTOR_META_FIELDS = {
    "id",
    "classification",
    "values",
    "emission_type_id",
    "is_conversion",
    "data_entry_type_id",
}


class FactorPayloadMixin(BaseModel):
    classification_fields: list[str] = []
    value_fields: list[str] = []

    @classmethod
    def numeric_fields(cls) -> set[str]:
        numeric = set()
        for name, field in cls.model_fields.items():
            anno = field.annotation
            if anno is None:
                continue
            origin = get_origin(anno)
            args = get_args(anno)
            if origin is None:
                if anno in (int, float):
                    numeric.add(name)
                continue
            if any(a in (int, float) for a in args):
                numeric.add(name)
        return numeric

    @model_validator(mode="before")
    @classmethod
    def coerce_numeric_strings(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        numeric_keys = cls.numeric_fields()

        def _coerce(payload: dict) -> dict:
            for key in numeric_keys:
                if key in payload and isinstance(payload[key], str):
                    try:
                        payload[key] = float(payload[key])
                    except ValueError:
                        continue
            return payload

        if "values" in values and isinstance(values["values"], dict):
            values["values"] = _coerce(values["values"])
        values = _coerce(values)
        return values


class FactorBase(BaseModel):
    """Base factor schema."""

    emission_type_id: int
    is_conversion: bool = False
    data_entry_type_id: int
    classification: Dict[str, Any] = Field(default_factory=dict)
    values: Dict[str, Any] = Field(default_factory=dict)


class FactorCreate(FactorPayloadMixin, FactorBase):
    """Schema for creating a factor."""

    pass


class FactorUpdate(FactorPayloadMixin, BaseModel):
    """Schema for updating a factor."""

    classification: Optional[Dict[str, Any]] = None
    values: Optional[Dict[str, Any]] = None


class FactorRead(FactorBase):
    """Schema for reading a factor."""

    id: int

    model_config = ConfigDict(from_attributes=True)


class FactorResponse(FactorRead):
    """API response schema for factor."""

    pass


class FactorResponseGen(FactorBase):
    """Response schema for factors."""

    id: int


T = TypeVar("T", bound=BaseModel, contravariant=True)


class FactorHandler(Protocol[T]):
    data_entry_type: Optional[DataEntryTypeEnum] = None
    emission_type: Optional[EmissionType] = None
    is_conversion: bool = False

    create_dto: Type[FactorCreate]
    update_dto: Type[FactorUpdate]
    response_dto: Type[FactorResponseGen]

    classification_fields: list[str]
    value_fields: list[str]

    @property
    def expected_columns(self) -> set[str]: ...
    @property
    def required_columns(self) -> set[str]: ...

    def to_response(self, factor: T) -> FactorResponseGen: ...
    def validate_create(self, payload: dict) -> FactorCreate: ...
    def validate_update(self, payload: dict) -> FactorUpdate: ...


FACTOR_HANDLERS: dict[DataEntryTypeEnum, FactorHandler] = {}


def get_factor_handler_by_data_entry_type(
    data_entry_type: DataEntryTypeEnum,
) -> FactorHandler:
    handler = FACTOR_HANDLERS.get(data_entry_type)
    if handler is None:
        raise ValueError(
            f"No factor handler found for data_entry_type={data_entry_type}"
        )
    return handler


class FactorHandlerMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        if name != "BaseFactorHandler" and bases:
            keys = getattr(cls, "registration_keys", None)
            if keys is None and getattr(cls, "data_entry_type", None) is not None:
                keys = [cls.data_entry_type]

            if keys:
                for key in keys:
                    FACTOR_HANDLERS[key] = cls()

        return cls


class BaseFactorHandler(metaclass=FactorHandlerMeta):
    """Base factor handler with common logic."""

    data_entry_type: Optional[DataEntryTypeEnum] = None
    emission_type: Optional[EmissionType] = None
    is_conversion: bool = False

    # These must be overridden in subclasses
    create_dto: Type[FactorCreate]
    update_dto: Type[FactorUpdate]
    response_dto: Type[FactorResponseGen]

    # These must be set for each handler, if not set, nothing will be registered
    registration_keys: Optional[list[DataEntryTypeEnum]] = None
    classification_fields: list[str] = []
    value_fields: list[str] = []

    @classmethod
    def get_by_type(cls, data_entry_type: DataEntryTypeEnum) -> "FactorHandler":
        handler = FACTOR_HANDLERS.get(data_entry_type)
        if handler is None:
            raise ValueError(
                f"No factor handler found for data_entry_type={data_entry_type}"
            )
        return handler

    def _prepare_payload(self, payload: dict) -> dict:
        prepared = dict(payload)
        if "emission_type_id" not in prepared and self.emission_type is not None:
            prepared["emission_type_id"] = self.emission_type.value
        if "is_conversion" not in prepared:
            prepared["is_conversion"] = self.is_conversion
        if "data_entry_type_id" not in prepared and self.data_entry_type is not None:
            prepared["data_entry_type_id"] = self.data_entry_type.value
        return prepared

    def to_response(self, factor: Factor) -> FactorResponseGen:
        payload = {
            "id": factor.id,
            "emission_type_id": factor.emission_type_id,
            "is_conversion": factor.is_conversion,
            "data_entry_type_id": factor.data_entry_type_id,
            **(factor.classification or {}),
            **(factor.values or {}),
        }
        return self.response_dto.model_validate(payload)

    @property
    def expected_columns(self) -> set[str]:
        """All CSV columns the handler's create DTO declares (minus meta fields)."""
        return set(self.create_dto.model_fields.keys()) - FACTOR_META_FIELDS

    @property
    def required_columns(self) -> set[str]:
        """Mandatory CSV columns (required in the create DTO, minus meta fields)."""
        return {
            name
            for name, f in self.create_dto.model_fields.items()
            if f.is_required() and name not in FACTOR_META_FIELDS
        }

    def validate_create(self, payload: dict) -> FactorCreate:
        return self.create_dto.model_validate(self._prepare_payload(payload))

    def validate_update(self, payload: dict) -> FactorUpdate:
        return self.update_dto.model_validate(self._prepare_payload(payload))


class ExternalCloudFactorResponse(FactorResponseGen):
    cloud_provider: str
    service_type: str
    factor_kgco2_per_eur: float


class ExternalAIFactorResponse(FactorResponseGen):
    ai_provider: str
    ai_use: str
    factor_gCO2eq: float


class TravelPlaneFactorResponse(FactorResponseGen):
    category: str
    ef_kg_co2eq_per_km: float
    rfi_adjustement: Optional[float] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None


class TravelTrainFactorResponse(FactorResponseGen):
    country_code: str
    ef_kg_co2eq_per_km: float


class ExternalCloudFactorCreate(FactorCreate):
    cloud_provider: str
    service_type: str
    factor_kgco2_per_eur: float

    classification_fields: list[str] = ["cloud_provider", "service_type"]
    value_fields: list[str] = ["factor_kgco2_per_eur"]


class ExternalCloudFactorUpdate(FactorUpdate):
    cloud_provider: Optional[str] = None
    service_type: Optional[str] = None
    factor_kgco2_per_eur: Optional[float] = None

    classification_fields: list[str] = ["cloud_provider", "service_type"]
    value_fields: list[str] = ["factor_kgco2_per_eur"]


class ExternalAIFactorCreate(FactorCreate):
    ai_provider: str
    ai_use: str
    factor_gCO2eq: float

    classification_fields: list[str] = ["ai_provider", "ai_use"]
    value_fields: list[str] = ["factor_gCO2eq"]


class ExternalAIFactorUpdate(FactorUpdate):
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    factor_gCO2eq: Optional[float] = None

    classification_fields: list[str] = ["ai_provider", "ai_use"]
    value_fields: list[str] = ["factor_gCO2eq"]


class TravelPlaneFactorCreate(FactorCreate):
    category: str
    ef_kg_co2eq_per_km: float
    rfi_adjustement: Optional[float] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None

    classification_fields: list[str] = ["category"]
    value_fields: list[str] = [
        "ef_kg_co2eq_per_km",
        "rfi_adjustement",
        "min_distance",
        "max_distance",
    ]


class TravelPlaneFactorUpdate(FactorUpdate):
    category: Optional[str] = None
    ef_kg_co2eq_per_km: Optional[float] = None
    rfi_adjustement: Optional[float] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None

    classification_fields: list[str] = ["category"]
    value_fields: list[str] = [
        "ef_kg_co2eq_per_km",
        "rfi_adjustement",
        "min_distance",
        "max_distance",
    ]


class TravelTrainFactorCreate(FactorCreate):
    country_code: str
    ef_kg_co2eq_per_km: float

    classification_fields: list[str] = ["country_code"]
    value_fields: list[str] = ["ef_kg_co2eq_per_km"]


class TravelTrainFactorUpdate(FactorUpdate):
    country_code: Optional[str] = None
    ef_kg_co2eq_per_km: Optional[float] = None

    classification_fields: list[str] = ["country_code"]
    value_fields: list[str] = ["ef_kg_co2eq_per_km"]


class ExternalCloudFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    emission_type: EmissionType = EmissionType.external__clouds__calcul

    create_dto = ExternalCloudFactorCreate
    update_dto = ExternalCloudFactorUpdate
    response_dto = ExternalCloudFactorResponse

    def _prepare_payload(self, payload: dict) -> dict:
        prepared = dict(payload)
        if "emission_type_id" not in prepared:
            service_type = prepared.get("service_type", "")
            emission_key = str(service_type).lower().strip() or "calcul"
            emission_type = EmissionType[emission_key]
            prepared["emission_type_id"] = emission_type.value
        return super()._prepare_payload(prepared)


class ExternalAIFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    # todo: resolver at runtime based on provider/use
    emission_type: EmissionType = EmissionType.external__ai

    create_dto = ExternalAIFactorCreate
    update_dto = ExternalAIFactorUpdate
    response_dto = ExternalAIFactorResponse


class TravelPlaneFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.plane
    emission_type: EmissionType = EmissionType.professional_travel__plane

    registration_keys = [DataEntryTypeEnum.plane]

    create_dto = TravelPlaneFactorCreate
    update_dto = TravelPlaneFactorUpdate
    response_dto = TravelPlaneFactorResponse


class TravelTrainFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.train
    emission_type: EmissionType = EmissionType.professional_travel__train

    registration_keys = [DataEntryTypeEnum.train]

    create_dto = TravelTrainFactorCreate
    update_dto = TravelTrainFactorUpdate
    response_dto = TravelTrainFactorResponse
