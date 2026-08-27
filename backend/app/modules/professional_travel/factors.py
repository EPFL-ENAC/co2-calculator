from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)


def _validate_non_negative_float(v: float | None, field_name: str) -> float | None:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


class TravelPlaneBase:
    category: str
    cabin_class: str
    ef_kg_co2eq_per_km: float
    rfi_adjustment: float
    min_distance: float
    max_distance: float


class _TravelPlaneBaseValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_km",
        "rfi_adjustment",
        "min_distance",
        "max_distance",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: str) -> str:
        valid_cabin_classes = [
            "economy",
            "business",
            "first",
        ]
        if not v:
            raise ValueError("Cabin class is required")
        if v not in valid_cabin_classes:
            raise ValueError("Invalid cabin class")
        return v

    @field_validator("category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not v:
            raise ValueError("Category is required")
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

    classification_fields: list[str] = ["category", "cabin_class"]
    value_fields: list[str] = [
        "ef_kg_co2eq_per_km",
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
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
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
