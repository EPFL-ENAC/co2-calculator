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


class ResearchFacilitiesCommonHandlerResponse(DataEntryResponseGen):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesCommonHandlerCreate(DataEntryCreate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesCommonHandlerUpdate(DataEntryUpdate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesCommonModuleHandler(BaseModuleHandler):
    """Handler for common research facilities data entries."""

    module_type: ModuleTypeEnum = ModuleTypeEnum.research_facilities
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.research_facilities,
    ]

    create_dto = ResearchFacilitiesCommonHandlerCreate
    update_dto = ResearchFacilitiesCommonHandlerUpdate
    response_dto = ResearchFacilitiesCommonHandlerResponse

    kind_field: str = "researchfacility_id"
    subkind_field: Optional[str] = None
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map: dict = {}

    def to_response(
        self, data_entry: DataEntry
    ) -> ResearchFacilitiesCommonHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> ResearchFacilitiesCommonHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ResearchFacilitiesCommonHandlerUpdate:
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
            Formula: (use / total_use) * kg_co2eq_sum, with unit check on use_unit.
            """
            use = ctx.get("use")
            use_unit = ctx.get("use_unit")
            if use is None or use_unit is None:
                return None
            # Must be same unit for the factor and the data entry to apply the formula
            use_unit_factor = factor_values.get("use_unit")
            if use_unit != use_unit_factor:
                return None
            # Compute share of use and apply to total emissions
            total_use = factor_values.get("total_use")
            kg_co2eq_sum = factor_values.get("kg_co2eq_sum")
            if total_use is None or kg_co2eq_sum is None:
                return None
            use_share = use / total_use if total_use > 0 else 0
            return use_share * kg_co2eq_sum

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_research_facilities_formula,
            )
        ]


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
    researchfacility_id: Optional[str] = None
    researchfacility_name: str
    use_unit: str
    kg_co2eq_sum: Optional[float] = None
    total_use: float

    @field_validator("total_use", mode="after")
    @classmethod
    def validate_total_use(cls, v: float) -> float:
        if v < 0:
            raise ValueError("total_use must be non-negative")
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
