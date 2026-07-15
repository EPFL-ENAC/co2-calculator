"""Research Facilities factor schemas and handlers (common + animal)."""

from typing import Optional

from pydantic import field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)

## RESEARCH FACILITIES FACTOR HANDLERS

# --- Common (research_facilities) ---

research_facilities_common_classification_fields: list[str] = [
    "researchfacility_id",
    "researchfacility_name",
]
research_facilities_common_value_fields: list[str] = [
    "use_unit",
    "kg_co2eq_sum",
    "total_use",
]


class ResearchFacilitiesCommonFactorCreate(FactorCreate):
    researchfacility_id: str
    researchfacility_name: str
    kg_co2eq_sum: Optional[float] = None
    total_use: float
    use_unit: str

    @field_validator("total_use", mode="after")
    @classmethod
    def validate_total_use(cls, v: float) -> float:
        if v < 0:
            raise ValueError("total_use must be non-negative")
        return v

    @field_validator("kg_co2eq_sum", mode="after")
    @classmethod
    def validate_kg_co2eq_sum(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("kg_co2eq_sum must be non-negative")
        return v


class ResearchFacilitiesCommonFactorUpdate(FactorUpdate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use_unit: Optional[str] = None
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None

    @field_validator("total_use", mode="after")
    @classmethod
    def validate_total_use(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("total_use must be non-negative")
        return v


class ResearchFacilitiesCommonFactorResponse(FactorResponseGen):
    researchfacility_id: Optional[str] = None
    researchfacility_name: str
    use_unit: str
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None


class ResearchFacilitiesCommonFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.research_facilities]
    emission_type = EmissionType.research_facilities__facilities

    create_dto = ResearchFacilitiesCommonFactorCreate
    update_dto = ResearchFacilitiesCommonFactorUpdate
    response_dto = ResearchFacilitiesCommonFactorResponse

    classification_fields: list[str] = research_facilities_common_classification_fields
    value_fields: list[str] = research_facilities_common_value_fields


## RESEARCH FACILITIES FACTOR HANDLERS

# --- Animal (mice_and_fish_animal_facilities) ---

research_facilities_animal_classification_fields: list[str] = [
    "researchfacility_id",
    "researchfacility_name",
    "researchfacility_type",
]
research_facilities_animal_value_fields: list[str] = [
    "processemissions_share",
    "building_energycombustions_share",
    "building_rooms_share",
    "purchases_common_share",
    "purchases_additional_share",
    "equipments_share",
    "kg_co2eq_sum_processemissions",
    "kg_co2eq_sum_building_energycombustions",
    "kg_co2eq_sum_building_rooms",
    "kg_co2eq_sum_purchases_common",
    "kg_co2eq_sum_purchases_additional",
    "kg_co2eq_sum_equipments",
    "use_unit",
    "total_use",
]


class ResearchFacilitiesAnimalFactorCreate(FactorCreate):
    researchfacility_id: str
    researchfacility_name: str
    researchfacility_type: str
    use_unit: str
    processemissions_share: float
    building_energycombustions_share: float
    building_rooms_share: float
    purchases_common_share: float
    purchases_additional_share: float
    equipments_share: float
    kg_co2eq_sum_processemissions: Optional[float] = None
    kg_co2eq_sum_building_energycombustions: Optional[float] = None
    kg_co2eq_sum_building_rooms: Optional[float] = None
    kg_co2eq_sum_purchases_common: Optional[float] = None
    kg_co2eq_sum_purchases_additional: Optional[float] = None
    kg_co2eq_sum_equipments: Optional[float] = None
    total_use: float

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    @field_validator("total_use", mode="after")
    @classmethod
    def validate_total_use(cls, v: float) -> float:
        if v < 0:
            raise ValueError("total_use must be non-negative")
        return v

    @field_validator(
        "processemissions_share",
        "building_energycombustions_share",
        "building_rooms_share",
        "purchases_common_share",
        "purchases_additional_share",
        "equipments_share",
        mode="after",
    )
    @classmethod
    def validate_share(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("Share values must be between 0 and 1")
        return v

    @field_validator(
        "kg_co2eq_sum_processemissions",
        "kg_co2eq_sum_building_energycombustions",
        "kg_co2eq_sum_building_rooms",
        "kg_co2eq_sum_purchases_common",
        "kg_co2eq_sum_purchases_additional",
        "kg_co2eq_sum_equipments",
        mode="after",
    )
    @classmethod
    def validate_kg_co2eq_sum(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("kg_co2eq_sum values must be non-negative")
        return v


class ResearchFacilitiesAnimalFactorUpdate(FactorUpdate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    researchfacility_type: Optional[str] = None
    use_unit: Optional[str] = None
    processemissions_share: Optional[float] = None
    building_energycombustions_share: Optional[float] = None
    building_rooms_share: Optional[float] = None
    purchases_common_share: Optional[float] = None
    purchases_additional_share: Optional[float] = None
    equipments_share: Optional[float] = None
    kg_co2eq_sum_processemissions: Optional[float] = None
    kg_co2eq_sum_building_energycombustions: Optional[float] = None
    kg_co2eq_sum_building_rooms: Optional[float] = None
    kg_co2eq_sum_purchases_common: Optional[float] = None
    kg_co2eq_sum_purchases_additional: Optional[float] = None
    kg_co2eq_sum_equipments: Optional[float] = None
    total_use: Optional[float] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesAnimalFactorResponse(FactorResponseGen):
    researchfacility_id: Optional[str] = None
    researchfacility_name: str
    researchfacility_type: Optional[str] = None
    use_unit: str
    processemissions_share: Optional[float] = None
    building_energycombustions_share: Optional[float] = None
    building_rooms_share: Optional[float] = None
    purchases_common_share: Optional[float] = None
    purchases_additional_share: Optional[float] = None
    equipments_share: Optional[float] = None
    kg_co2eq_sum_processemissions: Optional[float] = None
    kg_co2eq_sum_building_energycombustions: Optional[float] = None
    kg_co2eq_sum_building_rooms: Optional[float] = None
    kg_co2eq_sum_purchases_common: Optional[float] = None
    kg_co2eq_sum_purchases_additional: Optional[float] = None
    kg_co2eq_sum_equipments: Optional[float] = None
    total_use: Optional[float] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesAnimalFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.mice_and_fish_animal_facilities]
    emission_type = EmissionType.research_facilities__animal

    create_dto = ResearchFacilitiesAnimalFactorCreate
    update_dto = ResearchFacilitiesAnimalFactorUpdate
    response_dto = ResearchFacilitiesAnimalFactorResponse

    classification_fields: list[str] = research_facilities_animal_classification_fields
    value_fields: list[str] = research_facilities_animal_value_fields
