from typing import Optional

from sqlalchemy import func

from app.core.config import get_settings
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.equipment.data_entries import (
    MAX_WEEKLY_USAGE_HOURS,
    EquipmentHandlerCreate,
    EquipmentHandlerResponse,
    EquipmentHandlerUpdate,
)
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryUpdate,
)


class EquipmentModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.equipment
    data_entry_type: DataEntryTypeEnum | None = None
    category_field: str = "equipment_category"
    registration_keys = [
        DataEntryTypeEnum.it,
        DataEntryTypeEnum.scientific,
        DataEntryTypeEnum.other,
    ]
    # Allow subkind to be optional for equipment
    require_subkind_for_factor = False
    require_factor_to_match = False

    create_dto = EquipmentHandlerCreate
    update_dto = EquipmentHandlerUpdate
    response_dto = EquipmentHandlerResponse

    kind_field: str = "equipment_class"
    subkind_field: str = "sub_class"

    # Sort/filter keys MUST read from the same source `to_response` displays,
    # or the visible column won't match the ordering. equipment_class is shown
    # from DataEntry.data (the factor `class` lookup is a dead key); sub_class is
    # factor-preferred-then-data. Factor-only keys (active/standby_power_w) leave
    # rows with no matched emission-row factor id with a NULL sort key — which
    # is correct, since those rows display NULL for those fields too.
    sub_class_expr = func.coalesce(
        Factor.classification["sub_class"].as_string(),
        DataEntry.data["sub_class"].as_string(),
    )
    sort_map = {
        "id": DataEntry.id,
        "active_usage_hours_per_week": func.coalesce(
            DataEntry.data["active_usage_hours_per_week"].as_float(),
            Factor.values["active_usage_hours_per_week"].as_float(),
        ),
        "standby_usage_hours_per_week": func.coalesce(
            DataEntry.data["standby_usage_hours_per_week"].as_float(),
            Factor.values["standby_usage_hours_per_week"].as_float(),
        ),
        "name": DataEntry.data["name"].as_string(),
        "active_power_w": Factor.values["active_power_w"].as_float(),
        "standby_power_w": Factor.values["standby_power_w"].as_float(),
        "equipment_class": DataEntry.data["equipment_class"].as_string(),
        "sub_class": sub_class_expr,
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "equipment_class": DataEntry.data["equipment_class"].as_string(),
        "sub_class": sub_class_expr,
    }

    async def pre_compute(self, data_entry, session) -> dict:
        """Validate usage hours constraints (user data only)."""
        data = data_entry.data if hasattr(data_entry, "data") else {}

        active_hours = data.get("active_usage_hours_per_week")
        standby_hours = data.get("standby_usage_hours_per_week")

        if active_hours is None or standby_hours is None:
            return {}

        total_hours = float(active_hours) + float(standby_hours)
        if total_hours > MAX_WEEKLY_USAGE_HOURS:
            raise ValueError(
                "The sum of active_usage_hours_per_week and "
                "standby_usage_hours_per_week must be <= 168"
            )

        return {}

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _equipment_formula(ctx: dict, factor_values: dict) -> Optional[float]:
            # Usage hours are a live default: the user's value wins, an
            # unset field tracks the factor's current suggestion (nothing
            # is seeded into entry.data any more).
            active_hours = ctx.get("active_usage_hours_per_week")
            if active_hours is None:
                active_hours = factor_values.get("active_usage_hours_per_week")
            standby_hours = ctx.get("standby_usage_hours_per_week")
            if standby_hours is None:
                standby_hours = factor_values.get("standby_usage_hours_per_week")
            if active_hours is None or standby_hours is None:
                return None
            active_power_w = factor_values.get("active_power_w")
            standby_power_w = factor_values.get("standby_power_w")
            ef = factor_values.get("ef_kg_co2eq_per_kwh")
            if active_power_w is None or standby_power_w is None or ef is None:
                return None

            weekly_wh = (float(active_hours) * float(active_power_w)) + (
                float(standby_hours) * float(standby_power_w)
            )
            annual_kwh = (weekly_wh * get_settings().WEEKS_PER_YEAR) / 1000
            return annual_kwh * float(ef)

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_equipment_formula,
            )
        ]

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> EquipmentHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = data.get("primary_factor", {})
        new_entry = {
            "id": data_entry.id,
            "data_entry_type_id": data_entry.data_entry_type_id,
            "carbon_report_module_id": data_entry.carbon_report_module_id,
            **data,
            "active_power_w": primary_factor.get("active_power_w", None),
            "standby_power_w": primary_factor.get("standby_power_w", None),
            "active_usage_hours_per_week": (
                data.get("active_usage_hours_per_week")
                if data.get("active_usage_hours_per_week") is not None
                else primary_factor.get("active_usage_hours_per_week")
            ),
            "standby_usage_hours_per_week": (
                data.get("standby_usage_hours_per_week")
                if data.get("standby_usage_hours_per_week") is not None
                else primary_factor.get("standby_usage_hours_per_week")
            ),
            "equipment_class": primary_factor.get("class")
            or data.get("equipment_class"),
            "sub_class": primary_factor.get("sub_class") or data.get("sub_class"),
            "kg_co2eq": data.get("kg_co2eq", None),
        }
        return self.response_dto.model_validate(new_entry)

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)
