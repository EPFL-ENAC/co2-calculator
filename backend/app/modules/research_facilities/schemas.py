"""Research Facilities module handler."""

from typing import Optional

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
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

logger = get_logger(__name__)


class ResearchFacilitiesHandlerResponse(DataEntryResponseGen):
    name: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ResearchFacilitiesHandlerCreate(DataEntryCreate):
    name: Optional[str] = None


class ResearchFacilitiesHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None


class ResearchFacilitiesModuleHandler(BaseModuleHandler):
    """Handler for research facilities data entries (Strategy A — primary_factor_id).

    Formula: TBD (returns None until factors and a formula are defined).
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.internal_services
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.research_facilities,
        DataEntryTypeEnum.mice_and_fish_animal_facilities,
        DataEntryTypeEnum.other_research_facilities,
    ]

    create_dto = ResearchFacilitiesHandlerCreate
    update_dto = ResearchFacilitiesHandlerUpdate
    response_dto = ResearchFacilitiesHandlerResponse

    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map: dict = {}

    def to_response(self, data_entry: DataEntry) -> ResearchFacilitiesHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> ResearchFacilitiesHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ResearchFacilitiesHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:
        """Strategy A — primary_factor_id. Formula TBD; returns empty until defined."""

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                # Formula TBD — no emission rows until factors are defined
            )
        ]


## RESEARCH FACILITIES FACTOR HANDLERS

# --- Common (research_facilities) ---

research_facilities_common_classification_fields: list[str] = [
    "researchfacility_id",
    "researchfacility_name",
    "use_unit",
]
research_facilities_common_value_fields: list[str] = [
    "kg_co2eq_sum",
    "total_use",
]


class ResearchFacilitiesCommonFactorCreate(FactorCreate):
    researchfacility_id: Optional[int] = None
    researchfacility_name: str
    use_unit: str
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None


class ResearchFacilitiesCommonFactorUpdate(FactorUpdate):
    researchfacility_id: Optional[int] = None
    researchfacility_name: Optional[str] = None
    use_unit: Optional[str] = None
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None


class ResearchFacilitiesCommonFactorResponse(FactorResponseGen):
    researchfacility_id: Optional[int] = None
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


# --- Animal (mice_and_fish_animal_facilities) ---

research_facilities_animal_classification_fields: list[str] = [
    "researchfacility_id",
    "researchfacility_name",
    "researchfacility_type",
    "use_unit",
]
research_facilities_animal_value_fields: list[str] = [
    "processemissions_share",
    "building_energycombustions_share",
    "building_rooms_share",
    "purchases_common_share",
    "purchases_additional_share",
    "equipments_share",
    "kg_co2eq_sum",
    "total_use",
]


class ResearchFacilitiesAnimalFactorCreate(FactorCreate):
    researchfacility_id: Optional[int] = None
    researchfacility_name: str
    researchfacility_type: Optional[str] = None
    use_unit: str
    processemissions_share: Optional[float] = None
    building_energycombustions_share: Optional[float] = None
    building_rooms_share: Optional[float] = None
    purchases_common_share: Optional[float] = None
    purchases_additional_share: Optional[float] = None
    equipments_share: Optional[float] = None
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None


class ResearchFacilitiesAnimalFactorUpdate(FactorUpdate):
    researchfacility_id: Optional[int] = None
    researchfacility_name: Optional[str] = None
    researchfacility_type: Optional[str] = None
    use_unit: Optional[str] = None
    processemissions_share: Optional[float] = None
    building_energycombustions_share: Optional[float] = None
    building_rooms_share: Optional[float] = None
    purchases_common_share: Optional[float] = None
    purchases_additional_share: Optional[float] = None
    equipments_share: Optional[float] = None
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None


class ResearchFacilitiesAnimalFactorResponse(FactorResponseGen):
    researchfacility_id: Optional[int] = None
    researchfacility_name: str
    researchfacility_type: Optional[str] = None
    use_unit: str
    processemissions_share: Optional[float] = None
    building_energycombustions_share: Optional[float] = None
    building_rooms_share: Optional[float] = None
    purchases_common_share: Optional[float] = None
    purchases_additional_share: Optional[float] = None
    equipments_share: Optional[float] = None
    kg_co2eq_sum: Optional[float] = None
    total_use: Optional[float] = None


class ResearchFacilitiesAnimalFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.mice_and_fish_animal_facilities]
    emission_type = EmissionType.research_facilities__animal

    create_dto = ResearchFacilitiesAnimalFactorCreate
    update_dto = ResearchFacilitiesAnimalFactorUpdate
    response_dto = ResearchFacilitiesAnimalFactorResponse

    classification_fields: list[str] = research_facilities_animal_classification_fields
    value_fields: list[str] = research_facilities_animal_value_fields
