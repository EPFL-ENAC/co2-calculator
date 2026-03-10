"""Research Facilities module handler."""

from typing import Optional

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
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

    module_type: ModuleTypeEnum = ModuleTypeEnum.research_facilities
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.research_facilities,
        DataEntryTypeEnum.mice_and_fish_animal_facilities,
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
