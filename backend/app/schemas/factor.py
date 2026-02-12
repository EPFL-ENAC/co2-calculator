"""Factor schemas for API requests, responses, and CSV validation."""

from typing import Any, Dict, Optional, Protocol, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum
from app.models.factor import Factor
from app.models.location import TransportModeEnum

FACTOR_META_FIELDS = {
    "id",
    "classification",
    "values",
    "emission_type_id",
    "is_conversion",
    "data_entry_type_id",
}


class FactorPayloadMixin(BaseModel):
    classification_field_map: dict[str, str] = {}
    value_field_map: dict[str, str] = {}

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

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return {}

    @model_validator(mode="before")
    @classmethod
    def unflatten_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        if "classification" in values or "values" in values:
            return values

        new_payload = dict(values)
        classification: dict[str, Any] = {}
        values_dict: dict[str, Any] = {}

        for input_key, target_key in cls.classification_field_map.items():
            if input_key in values:
                raw_val = values.get(input_key)
                classification[target_key] = None if raw_val == "" else raw_val

        for input_key, target_key in cls.value_field_map.items():
            if input_key in values:
                values_dict[target_key] = values.get(input_key)

        classification.update(cls.computed_classification(values))

        new_payload["classification"] = classification
        new_payload["values"] = values_dict
        return new_payload

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
    factor_variant: Optional[str] = None
    emission_type: Optional[EmissionTypeEnum] = None
    is_conversion: bool = False

    create_dto: Type[FactorCreate]
    update_dto: Type[FactorUpdate]
    response_dto: Type[FactorResponseGen]

    def to_response(self, factor: T) -> FactorResponseGen: ...
    def validate_create(self, payload: dict) -> FactorCreate: ...
    def validate_update(self, payload: dict) -> FactorUpdate: ...


FACTOR_HANDLERS: dict[tuple[DataEntryTypeEnum, Optional[str]], FactorHandler] = {}


class FactorHandlerMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        if name != "BaseFactorHandler" and bases:
            keys = getattr(cls, "registration_keys", None)
            if keys is None and getattr(cls, "data_entry_type", None) is not None:
                keys = [(cls.data_entry_type, getattr(cls, "factor_variant", None))]

            if keys:
                for key in keys:
                    FACTOR_HANDLERS[key] = cls()

        return cls


class BaseFactorHandler(metaclass=FactorHandlerMeta):
    """Base factor handler with common logic."""

    data_entry_type: Optional[DataEntryTypeEnum] = None
    factor_variant: Optional[str] = None
    emission_type: Optional[EmissionTypeEnum] = None
    is_conversion: bool = False

    # These must be overridden in subclasses
    create_dto: Type[FactorCreate]
    update_dto: Type[FactorUpdate]
    response_dto: Type[FactorResponseGen]

    @classmethod
    def get_by_type(
        cls, data_entry_type: DataEntryTypeEnum, variant: Optional[str] = None
    ) -> "FactorHandler":
        handler = FACTOR_HANDLERS.get((data_entry_type, variant))
        if handler is None:
            raise ValueError(
                "No factor handler found for "
                f"data_entry_type={data_entry_type}, variant={variant}"
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

    def validate_create(self, payload: dict) -> FactorCreate:
        return self.create_dto.model_validate(self._prepare_payload(payload))

    def validate_update(self, payload: dict) -> FactorUpdate:
        return self.update_dto.model_validate(self._prepare_payload(payload))


class EquipmentFactorResponse(FactorResponseGen):
    equipment_class: str
    sub_class: Optional[str] = None
    active_power_w: float
    standby_power_w: float


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
    impact_score: float
    rfi_adjustment: Optional[float] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None


class TravelTrainFactorResponse(FactorResponseGen):
    country_code: str
    impact_score: float


class EquipmentFactorCreate(FactorCreate):
    equipment_class: str
    sub_class: Optional[str] = None
    active_power_w: float
    standby_power_w: float

    classification_field_map: dict[str, str] = {
        "equipment_class": "class",
        "sub_class": "sub_class",
    }
    value_field_map: dict[str, str] = {
        "active_power_w": "active_power_w",
        "standby_power_w": "standby_power_w",
    }

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        equipment_class = payload.get("equipment_class")
        sub_class = payload.get("sub_class")
        return {
            "kind": equipment_class,
            "subkind": sub_class or None,
        }


class EquipmentFactorUpdate(FactorUpdate):
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None
    active_power_w: Optional[float] = None
    standby_power_w: Optional[float] = None

    classification_field_map: dict[str, str] = {
        "equipment_class": "class",
        "sub_class": "sub_class",
    }
    value_field_map: dict[str, str] = {
        "active_power_w": "active_power_w",
        "standby_power_w": "standby_power_w",
    }

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return EquipmentFactorCreate.computed_classification(payload)


class ExternalCloudFactorCreate(FactorCreate):
    cloud_provider: str
    service_type: str
    factor_kgco2_per_eur: float

    classification_field_map: dict[str, str] = {
        "cloud_provider": "cloud_provider",
        "service_type": "service_type",
    }
    value_field_map: dict[str, str] = {"factor_kgco2_per_eur": "factor_kgco2_per_eur"}

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return {
            "kind": payload.get("cloud_provider"),
            "subkind": payload.get("service_type"),
        }


class ExternalCloudFactorUpdate(FactorUpdate):
    cloud_provider: Optional[str] = None
    service_type: Optional[str] = None
    factor_kgco2_per_eur: Optional[float] = None

    classification_field_map: dict[str, str] = {
        "cloud_provider": "cloud_provider",
        "service_type": "service_type",
    }
    value_field_map: dict[str, str] = {"factor_kgco2_per_eur": "factor_kgco2_per_eur"}

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return ExternalCloudFactorCreate.computed_classification(payload)


class ExternalAIFactorCreate(FactorCreate):
    ai_provider: str
    ai_use: str
    factor_gCO2eq: float

    classification_field_map: dict[str, str] = {
        "ai_provider": "ai_provider",
        "ai_use": "ai_use",
    }
    value_field_map: dict[str, str] = {"factor_gCO2eq": "factor_gCO2eq"}

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return {
            "kind": payload.get("ai_provider"),
            "subkind": payload.get("ai_use"),
        }


class ExternalAIFactorUpdate(FactorUpdate):
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    factor_gCO2eq: Optional[float] = None

    classification_field_map: dict[str, str] = {
        "ai_provider": "ai_provider",
        "ai_use": "ai_use",
    }
    value_field_map: dict[str, str] = {"factor_gCO2eq": "factor_gCO2eq"}

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return ExternalAIFactorCreate.computed_classification(payload)


class TravelPlaneFactorCreate(FactorCreate):
    category: str
    impact_score: float
    rfi_adjustment: Optional[float] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None

    classification_field_map: dict[str, str] = {"category": "category"}
    value_field_map: dict[str, str] = {
        "impact_score": "impact_score",
        "rfi_adjustment": "rfi_adjustment",
        "min_distance": "min_distance",
        "max_distance": "max_distance",
    }

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return {
            "kind": TransportModeEnum.plane.value,
            "subkind": payload.get("category"),
        }


class TravelPlaneFactorUpdate(FactorUpdate):
    category: Optional[str] = None
    impact_score: Optional[float] = None
    rfi_adjustment: Optional[float] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None

    classification_field_map: dict[str, str] = {"category": "category"}
    value_field_map: dict[str, str] = {
        "impact_score": "impact_score",
        "rfi_adjustment": "rfi_adjustment",
        "min_distance": "min_distance",
        "max_distance": "max_distance",
    }

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return TravelPlaneFactorCreate.computed_classification(payload)


class TravelTrainFactorCreate(FactorCreate):
    country_code: str
    impact_score: float

    classification_field_map: dict[str, str] = {"country_code": "country_code"}
    value_field_map: dict[str, str] = {"impact_score": "impact_score"}

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return {
            "kind": TransportModeEnum.train.value,
            "subkind": payload.get("country_code"),
        }


class TravelTrainFactorUpdate(FactorUpdate):
    country_code: Optional[str] = None
    impact_score: Optional[float] = None

    classification_field_map: dict[str, str] = {"country_code": "country_code"}
    value_field_map: dict[str, str] = {"impact_score": "impact_score"}

    @classmethod
    def computed_classification(cls, payload: dict) -> dict:
        return TravelTrainFactorCreate.computed_classification(payload)


class EquipmentFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        (DataEntryTypeEnum.scientific, None),
        (DataEntryTypeEnum.it, None),
        (DataEntryTypeEnum.other, None),
    ]
    emission_type: EmissionTypeEnum = EmissionTypeEnum.equipment

    create_dto = EquipmentFactorCreate
    update_dto = EquipmentFactorUpdate
    response_dto = EquipmentFactorResponse

    def to_response(self, factor: Factor) -> FactorResponseGen:
        payload = {
            "id": factor.id,
            "emission_type_id": factor.emission_type_id,
            "is_conversion": factor.is_conversion,
            "data_entry_type_id": factor.data_entry_type_id,
            "equipment_class": factor.classification.get("class"),
            "sub_class": factor.classification.get("sub_class"),
            "active_power_w": factor.values.get("active_power_w"),
            "standby_power_w": factor.values.get("standby_power_w"),
        }
        return self.response_dto.model_validate(payload)


class ExternalCloudFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    emission_type: EmissionTypeEnum = EmissionTypeEnum.calcul

    create_dto = ExternalCloudFactorCreate
    update_dto = ExternalCloudFactorUpdate
    response_dto = ExternalCloudFactorResponse

    def _prepare_payload(self, payload: dict) -> dict:
        prepared = dict(payload)
        if "emission_type_id" not in prepared:
            service_type = prepared.get("service_type", "")
            emission_key = str(service_type).lower().strip() or "calcul"
            emission_type = EmissionTypeEnum[emission_key]
            prepared["emission_type_id"] = emission_type.value
        return super()._prepare_payload(prepared)


class ExternalAIFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    emission_type: EmissionTypeEnum = EmissionTypeEnum.ai_provider

    create_dto = ExternalAIFactorCreate
    update_dto = ExternalAIFactorUpdate
    response_dto = ExternalAIFactorResponse


class TravelPlaneFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.trips
    factor_variant: str = "plane"
    emission_type: EmissionTypeEnum = EmissionTypeEnum.plane

    registration_keys = [(DataEntryTypeEnum.trips, "plane")]

    create_dto = TravelPlaneFactorCreate
    update_dto = TravelPlaneFactorUpdate
    response_dto = TravelPlaneFactorResponse


class TravelTrainFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.trips
    factor_variant: str = "train"
    emission_type: EmissionTypeEnum = EmissionTypeEnum.train

    registration_keys = [(DataEntryTypeEnum.trips, "train")]

    create_dto = TravelTrainFactorCreate
    update_dto = TravelTrainFactorUpdate
    response_dto = TravelTrainFactorResponse
