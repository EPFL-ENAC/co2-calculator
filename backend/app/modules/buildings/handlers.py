from typing import Any, Optional

from sqlmodel import func

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    FactorQuery,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.buildings.data_entries import (
    BuildingEmbodiedEnergyHandlerCreate,
    BuildingEmbodiedEnergyHandlerResponse,
    BuildingEmbodiedEnergyHandlerUpdate,
    BuildingRoomHandlerCreate,
    BuildingRoomHandlerResponse,
    BuildingRoomHandlerUpdate,
    EnergyCombustionHandlerCreate,
    EnergyCombustionHandlerResponse,
    EnergyCombustionHandlerUpdate,
)
from app.modules.emissions import EmissionType
from app.schemas.data_entry import BaseModuleHandler
from app.services.building_room_service import BuildingRoomService

logger = get_logger(__name__)


class BuildingRoomModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.building

    create_dto = BuildingRoomHandlerCreate
    update_dto = BuildingRoomHandlerUpdate
    response_dto = BuildingRoomHandlerResponse

    kind_field: str = "building_name"
    subkind_field: str = "room_type"
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "building_name": DataEntry.data["building_name"].as_string(),
        "room_name": DataEntry.data["room_name"].as_string(),
        "room_type": DataEntry.data["room_type"].as_string(),
        "room_surface_square_meter": DataEntry.data[
            "room_surface_square_meter"
        ].as_float(),
        "room_allocation_ratio": DataEntry.data["room_allocation_ratio"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "building_name": DataEntry.data["building_name"].as_string(),
        "room_name": DataEntry.data["room_name"].as_string(),
        "room_type": DataEntry.data["room_type"].as_string(),
    }

    # Maps each building EmissionType leaf → factor field for kwh/m².
    _EMISSION_TO_KWH_FIELD: dict = {
        EmissionType.buildings__rooms__lighting: "lighting_kwh_per_square_meter",
        EmissionType.buildings__rooms__cooling: "cooling_kwh_per_square_meter",
        EmissionType.buildings__rooms__ventilation: "ventilation_kwh_per_square_meter",
        EmissionType.buildings__rooms__heating_electric: "heating_kwh_per_square_meter",
        EmissionType.buildings__rooms__heating_thermal: "heating_kwh_per_square_meter",
    }

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """call RoomService to get room surface by room_name"""
        room_name = data_entry.data.get("room_name")
        building_name = data_entry.data.get("building_name")
        if not room_name or not building_name:
            # Surface missing reference rows in the logs — the entry
            # persists but produces no emission leaves (the workflow's
            # "skip, don't default" semantic).  Without this warning,
            # operators couldn't tell why a row uploaded but
            # contributed zero to the module's totals.
            logger.warning(
                "buildings.pre_compute: skipping entry id=%s — missing "
                "room_name or building_name (room_name=%r, building_name=%r)",
                getattr(data_entry, "id", None),
                room_name,
                building_name,
            )
            return {}
        service = BuildingRoomService(session)
        room = await service.get_room(room_name=room_name)
        if room is None:
            # Same "no leaf rows" outcome as the missing-name branch
            # above — log so the operator can chase the missing
            # building_room reference (likely a stale CSV or a
            # building_rooms ref-data import that didn't run).
            logger.warning(
                "buildings.pre_compute: skipping entry id=%s — room not "
                "found in BuildingRoom ref-data (room_name=%r, "
                "building_name=%r)",
                getattr(data_entry, "id", None),
                room_name,
                building_name,
            )
        return {
            "room_surface_square_meter": room.room_surface_square_meter
            if room
            else None
        }

    @staticmethod
    def _compute_kwh_emission(
        ctx: dict,
        factor_values: dict,
        kwh_field: str,
    ) -> float | None:
        """Compute kg_co2eq from surface × kwh_per_m² × ef × conversion."""
        # room_surface_square_meter should be resolve like travel! from room

        surface = ctx.get("room_surface_square_meter")
        ratio = ctx.get("room_allocation_ratio")
        kwh_per_m2 = factor_values.get(kwh_field)
        ef = factor_values.get("ef_kg_co2eq_per_kwh")
        if surface is None or kwh_per_m2 is None or ef is None:
            return None

        # ratio is already validated to be in [0, 1],
        # set a default value of 1.0 if not provided
        ratio_nb = float(ratio) if ratio is not None else 1.0

        # Heating carries a conversion_factor (primary energy → final energy);
        # the correct electric/thermal leaf is already chosen upstream, so it
        # applies directly. Other energy types have no conversion (default 1.0).
        # An explicit `is None` check keeps a legitimate 0.0 (e.g. carbon-free
        # network) from being silently coerced to 1.0.
        conversion_factor = 1.0
        if kwh_field == "heating_kwh_per_square_meter":
            override = factor_values.get("conversion_factor")
            if override is not None:
                conversion_factor = override
        kwh = float(surface) * float(kwh_per_m2) * ratio_nb
        return kwh * float(ef) * float(conversion_factor)

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:
        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        # Try direct match, then fall back to parent (WW→ZZ)
        kwh_field = self._EMISSION_TO_KWH_FIELD.get(emission_type)
        if not kwh_field and emission_type.parent is not None:
            kwh_field = self._EMISSION_TO_KWH_FIELD.get(emission_type.parent)
        if not kwh_field:
            return []

        def _building_formula(ctx: dict, factor_values: dict) -> float | None:
            return self._compute_kwh_emission(ctx, factor_values, kwh_field)

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_building_formula,
            )
        ]

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> BuildingRoomHandlerResponse:
        d = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = d.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
                "room_type": d.get("room_type"),
                "heating_kwh_per_square_meter": primary_factor.get(
                    "heating_kwh_per_square_meter", None
                ),
                "cooling_kwh_per_square_meter": primary_factor.get(
                    "cooling_kwh_per_square_meter", None
                ),
                "ventilation_kwh_per_square_meter": primary_factor.get(
                    "ventilation_kwh_per_square_meter", None
                ),
                "lighting_kwh_per_square_meter": primary_factor.get(
                    "lighting_kwh_per_square_meter", None
                ),
            }
        )

    def validate_create(self, payload: dict) -> BuildingRoomHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> BuildingRoomHandlerUpdate:
        return self.update_dto.model_validate(payload)


class EnergyCombustionModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.energy_combustion

    create_dto = EnergyCombustionHandlerCreate
    update_dto = EnergyCombustionHandlerUpdate
    response_dto = EnergyCombustionHandlerResponse

    kind_field: str = "name"
    subkind_field: str | None = None
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        # Same coalesce as filter_map — sort must follow the displayed value.
        "name": func.coalesce(
            Factor.classification["name"].as_string(),
            DataEntry.data["name"].as_string(),
        ),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        # Factor value when matched, entry data otherwise — search must find
        # the same value the row displays.
        "name": func.coalesce(
            Factor.classification["name"].as_string(),
            DataEntry.data["name"].as_string(),
        ),
    }

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_key="ef_kg_co2eq_per_unit",
                quantity_key="quantity",
            )
        ]

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> EnergyCombustionHandlerResponse:
        d = enriched_data if enriched_data is not None else data_entry.data
        # primary_factor is a flat dict of factor.values merged with
        # factor.classification (see DataEntryRepository.get_submodule_data).
        # Read fields directly off the flat dict — there is no nested "values".
        primary_factor = d.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
                "name": primary_factor.get("kind") or d.get("name"),
                "unit": primary_factor.get("unit") or d.get("unit"),
            }
        )

    def validate_create(self, payload: dict) -> EnergyCombustionHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> EnergyCombustionHandlerUpdate:
        return self.update_dto.model_validate(payload)


class BuildingEmbodiedEnergyModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.building_embodied_energy

    create_dto = BuildingEmbodiedEnergyHandlerCreate
    update_dto = BuildingEmbodiedEnergyHandlerUpdate
    response_dto = BuildingEmbodiedEnergyHandlerResponse

    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        # Same coalesce as filter_map — sort must follow the displayed value.
        "building_name": func.coalesce(
            Factor.classification["building_name"].as_string(),
            DataEntry.data["building_name"].as_string(),
        ),
    }

    filter_map = {
        "building_name": func.coalesce(
            Factor.classification["building_name"].as_string(),
            DataEntry.data["building_name"].as_string(),
        ),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> BuildingEmbodiedEnergyHandlerResponse:
        d = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
                "building_name": d.get("building_name"),
            }
        )

    def validate_create(self, payload: dict) -> BuildingEmbodiedEnergyHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> BuildingEmbodiedEnergyHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx):
        if emission_type != EmissionType.buildings__construction_and_renovation:
            return []

        def _building_embodied_energy_formula(
            ctx: dict, factor_values: dict
        ) -> float | None:
            surface = ctx.get("room_surface_square_meter")
            ef_kgco2eq_per_m2 = factor_values.get("ef_kgco2eq_per_m2")
            # If any of the required values are missing, we cannot compute the emissions
            if surface is None or ef_kgco2eq_per_m2 is None:
                return None
            return float(surface) * float(ef_kgco2eq_per_m2)

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.building_embodied_energy,
                    kind=None,
                    subkind=None,
                    context={"building_name": data_entry.data.get("building_name")},
                    fallbacks={"building_name": "default"},
                ),
                formula_func=_building_embodied_energy_formula,
            )
        ]
