from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
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


buildings_classification_fields: list[str] = [
    "building_name",
    "room_type",
    "energy_type",
]
buildings_value_fields: list[str] = [
    "ef_kg_co2eq_per_kwh",
    "heating_kwh_per_square_meter",
    "cooling_kwh_per_square_meter",
    "ventilation_kwh_per_square_meter",
    "lighting_kwh_per_square_meter",
    "conversion_factor",
]


class _BuildingsFactorValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_kwh",
        "heating_kwh_per_square_meter",
        "cooling_kwh_per_square_meter",
        "ventilation_kwh_per_square_meter",
        "lighting_kwh_per_square_meter",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        valid_room_types = [
            "office",
            "miscellaneous",
            "laboratories",
            "archives",
            "libraries",
            "auditoriums",
            None,
        ]
        if not v:
            raise ValueError("Room type is required")
        if v not in valid_room_types:
            raise ValueError("Invalid room type")
        return v

    @field_validator("energy_type", mode="after")
    @classmethod
    def validate_energy_type(cls, v: str) -> str:
        valid_energy_types = [
            "electric",
            "thermal",
        ]
        # Normalize aliases
        normalized = v.lower() if v else v
        if not normalized:
            raise ValueError("Energy type is required")
        if normalized not in valid_energy_types:
            raise ValueError(
                f"Invalid energy type: {v}. Must be one of: electric, thermal"
            )
        return normalized


class BuildingBaseFactor:
    building_name: str
    room_type: str
    heating_kwh_per_square_meter: float
    cooling_kwh_per_square_meter: float
    ventilation_kwh_per_square_meter: float
    lighting_kwh_per_square_meter: float
    ef_kg_co2eq_per_kwh: float
    energy_type: str
    conversion_factor: float | None = 1


class BuildingsFactorCreate(
    _BuildingsFactorValidationMixin, FactorCreate, BuildingBaseFactor
):
    pass


class BuildingsFactorUpdate(
    _BuildingsFactorValidationMixin, FactorUpdate, BuildingBaseFactor
):
    pass


class BuildingsFactorResponse(FactorResponseGen, BuildingBaseFactor):
    pass


class BuildingsFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.building,
    ]
    emission_type: EmissionType = EmissionType.buildings__rooms

    create_dto = BuildingsFactorCreate
    update_dto = BuildingsFactorUpdate
    response_dto = BuildingsFactorResponse

    classification_fields: list[str] = buildings_classification_fields
    value_fields: list[str] = buildings_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)


energy_combustion_classification_fields: list[str] = ["unit", "name"]
energy_combustion_value_fields: list[str] = [
    "ef_kg_co2eq_per_unit",
]


class _EnergyCombustionFactorValidationMixin:
    @field_validator("ef_kg_co2eq_per_unit", mode="after")
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")


class EnergyCombustionFactorCreate(
    _EnergyCombustionFactorValidationMixin, FactorCreate
):
    # data_entry_type: str #only for upload in datamanagement
    unit: str
    name: str
    ef_kg_co2eq_per_unit: float


class EnergyCombustionFactorUpdate(
    _EnergyCombustionFactorValidationMixin, FactorUpdate
):
    unit: str | None = None
    name: str | None = None
    ef_kg_co2eq_per_unit: float | None = None


class EnergyCombustionFactorResponse(FactorResponseGen):
    unit: str
    name: str
    ef_kg_co2eq_per_unit: float


class EnergyCombustionFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.energy_combustion,
    ]
    emission_type: EmissionType = EmissionType.buildings__combustion

    create_dto = EnergyCombustionFactorCreate
    update_dto = EnergyCombustionFactorUpdate
    response_dto = EnergyCombustionFactorResponse

    classification_fields: list[str] = energy_combustion_classification_fields
    value_fields: list[str] = energy_combustion_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)


class BuildingEmbodiedEnergyFactorCreate(FactorCreate):
    building_name: str
    category: str
    ef_kgco2eq_per_m2: float

    @field_validator("ef_kgco2eq_per_m2", mode="after")
    @classmethod
    def validate_ef_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")


class BuildingEmbodiedEnergyFactorUpdate(FactorUpdate):
    building_name: str | None = None
    category: str | None = None
    ef_kgco2eq_per_m2: float | None = None

    @field_validator("ef_kgco2eq_per_m2", mode="after")
    @classmethod
    def validate_ef_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")


class BuildingEmbodiedEnergyFactorResponse(FactorResponseGen):
    building_name: str
    category: str
    ef_kgco2eq_per_m2: float

    @field_validator("category", mode="after")
    @classmethod
    def _non_empty(cls, v: str, info: ValidationInfo) -> str:
        CATEGORY_VALUES = {"new-tech", "new-env", "ren-tech", "ren-env", "demolition"}
        if not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        # should be amongst new-tech, new-env,ren-tech,ren-env,demolition
        if v.strip() not in CATEGORY_VALUES:
            raise ValueError(
                f"{info.field_name} must be one of {sorted(CATEGORY_VALUES)}"
            )
        return v.strip()


class BuildingEmbodiedEnergyFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.building_embodied_energy,
    ]
    emission_type: EmissionType = EmissionType.buildings__construction_and_renovation

    create_dto = BuildingEmbodiedEnergyFactorCreate
    update_dto = BuildingEmbodiedEnergyFactorUpdate
    response_dto = BuildingEmbodiedEnergyFactorResponse

    classification_fields: list[str] = ["building_name", "category"]
    value_fields: list[str] = ["ef_kgco2eq_per_m2"]

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)
