"""Research Facilities module handlers (common + animal)."""

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
)
from app.models.module_type import ModuleTypeEnum
from app.modules.research_facilities.data_entries import (
    ResearchFacilitiesAnimalHandlerCreate,
    ResearchFacilitiesAnimalHandlerResponse,
    ResearchFacilitiesAnimalHandlerUpdate,
    ResearchFacilitiesCommonHandlerCreate,
    ResearchFacilitiesCommonHandlerResponse,
    ResearchFacilitiesCommonHandlerUpdate,
)
from app.schemas.data_entry import BaseModuleHandler


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
    subkind_field: str | None = None
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "researchfacility_id": DataEntry.data["researchfacility_id"].as_string(),
        "researchfacility_name": DataEntry.data["researchfacility_name"].as_string(),
        "use": DataEntry.data["use"].as_float(),
        "use_unit": DataEntry.data["use_unit"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map: dict = {
        "researchfacility_id": DataEntry.data["researchfacility_id"].as_string(),
        "researchfacility_name": DataEntry.data["researchfacility_name"].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ResearchFacilitiesCommonHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
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
        ) -> float | None:
            """Formula: (use / total_use) * kg_co2eq_sum, checking use_unit."""
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
                factor_id=factor_id,
                formula_func=_research_facilities_formula,
            )
        ]


class ResearchFacilitiesAnimalModuleHandler(BaseModuleHandler):
    """Handler for research facilities data entries related
    to rodent and fish animal facilities.
    """

    module_type: ModuleTypeEnum = ModuleTypeEnum.research_facilities
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.animal_facilities,
    ]

    create_dto = ResearchFacilitiesAnimalHandlerCreate
    update_dto = ResearchFacilitiesAnimalHandlerUpdate
    response_dto = ResearchFacilitiesAnimalHandlerResponse

    kind_field: str = "researchfacility_id"
    subkind_field: str = "researchfacility_type"
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "researchfacility_id": DataEntry.data["researchfacility_id"].as_string(),
        "researchfacility_name": DataEntry.data["researchfacility_name"].as_string(),
        "researchfacility_type": DataEntry.data["researchfacility_type"].as_string(),
        "use": DataEntry.data["use"].as_float(),
        "use_unit": DataEntry.data["use_unit"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map: dict = {
        "researchfacility_id": DataEntry.data["researchfacility_id"].as_string(),
        "researchfacility_name": DataEntry.data["researchfacility_name"].as_string(),
        "researchfacility_type": DataEntry.data["researchfacility_type"].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ResearchFacilitiesAnimalHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
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
        ) -> float | None:
            """Compute emissions based on share of use of the facility compared
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
            use_share = use / total_use if total_use > 0 else 0.0
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
                kg_co2eq_sum_source = factor_values.get(f"kg_co2eq_sum_{source}")
                if kg_co2eq_sum_source is not None:
                    # Add provided facility emissions modulo share of use
                    if kg_co2eq_sum is None:
                        kg_co2eq_sum = 0
                    kg_co2eq_sum += use_share * kg_co2eq_sum_source
                else:
                    # Source emissions are missing in the factor values
                    researchfacility_name = ctx.get("researchfacility_name", "Unknown")
                    researchfacility_type = ctx.get("researchfacility_type", "Unknown")
                    raise ValueError(
                        f"Missing kg_co2eq_sum for source {source} in factor values "
                        f"for facility {researchfacility_name} "
                        f"({researchfacility_type})."
                    )
            return kg_co2eq_sum

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_research_facilities_formula,
            )
        ]
