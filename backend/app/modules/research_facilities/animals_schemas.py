"""Research Facilities module handler."""

from typing import Optional

from pydantic import field_validator

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


class ResearchFacilitiesAnimalHandlerResponse(DataEntryResponseGen):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ResearchFacilitiesAnimalHandlerCreate(DataEntryCreate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None


class ResearchFacilitiesAnimalHandlerUpdate(DataEntryUpdate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None


class ResearchFacilitiesAnimalModuleHandler(BaseModuleHandler):
    """Handler for research facilities data entries related
    to mice and fish animal facilities.
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.research_facilities
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.mice_and_fish_animal_facilities,
    ]

    create_dto = ResearchFacilitiesAnimalHandlerCreate
    update_dto = ResearchFacilitiesAnimalHandlerUpdate
    response_dto = ResearchFacilitiesAnimalHandlerResponse

    kind_field: str = "researchfacility_id"
    subkind_field: str = "researchfacility_type"
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map: dict = {}

    def to_response(
        self, data_entry: DataEntry
    ) -> ResearchFacilitiesAnimalHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> ResearchFacilitiesAnimalHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ResearchFacilitiesAnimalHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:
        """Strategy A — primary_factor_id."""

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _research_facilities_formula(
            ctx: dict, factor_values: dict
        ) -> Optional[float]:
            """
            Compute emissions based on share of use of the facility compared
            to total use.
            Formula: (use / total_use) * kg_co2eq_sum, for each sources,
            with unit check on use_unit.
            """
            use = ctx.get("use")
            use_unit = ctx.get("use_unit")
            if use is None or use_unit is None:
                return None
            # Must be same unit for the factor and the data entry to apply the formula
            use_unit_factor = factor_values.get("use_unit")
            if use_unit != use_unit_factor:
                return None
            # Compute share of use and apply to each source emissions
            # and sum them up.
            total_use = factor_values.get("total_use")
            if total_use is None:
                return None
            sources = [
                "processemissions",
                "building_energycombustions",
                "building_rooms",
                "purchases_common",
                "purchases_additional",
                "equipments",
            ]
            kg_co2eq_sum = None
            for source in sources:
                source_share = factor_values.get(f"{source}_share")
                kg_co2eq_sum_source = factor_values.get(f"kg_co2eq_sum_{source}")
                if source_share is None or kg_co2eq_sum_source is None:
                    continue
                if kg_co2eq_sum is None:
                    kg_co2eq_sum = 0
                kg_co2eq_sum += (
                    use * source_share / total_use if total_use > 0 else 0
                ) * kg_co2eq_sum_source
            return kg_co2eq_sum

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_research_facilities_formula,
            )
        ]


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
    def validate_share(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0 or v > 1:
            raise ValueError("Share values must be between 0 and 1")
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
