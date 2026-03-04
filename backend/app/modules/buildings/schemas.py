from typing import Any, Optional

from pydantic import field_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
    FactorQuery,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class BuildingRoomHandlerResponse(DataEntryResponseGen):
    building_name: str
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None
    heating_kwh_per_m2: Optional[float] = None
    cooling_kwh_per_m2: Optional[float] = None
    ventilation_kwh_per_m2: Optional[float] = None
    lighting_kwh_per_m2: Optional[float] = None
    heating_kwh: Optional[float] = None
    cooling_kwh: Optional[float] = None
    ventilation_kwh: Optional[float] = None
    lighting_kwh: Optional[float] = None
    kg_co2eq: Optional[float] = None


class BuildingRoomHandlerCreate(DataEntryCreate):
    building_name: str
    room_name: str
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None
    heating_kwh_per_square_meter: Optional[float] = None
    cooling_kwh_per_square_meter: Optional[float] = None
    ventilation_kwh_per_square_meter: Optional[float] = None
    lighting_kwh_per_square_meter: Optional[float] = None
    note: Optional[str] = None

    @field_validator("room_surface_square_meter", mode="after")
    @classmethod
    def validate_surface(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Surface must be > 0")
        return v


class BuildingRoomHandlerUpdate(DataEntryUpdate):
    building_name: Optional[str] = None
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None
    heating_kwh_per_square_meter: Optional[float] = None
    cooling_kwh_per_square_meter: Optional[float] = None
    ventilation_kwh_per_square_meter: Optional[float] = None
    lighting_kwh_per_square_meter: Optional[float] = None
    note: Optional[str] = None

    @field_validator("room_surface_square_meter", mode="after")
    @classmethod
    def validate_surface(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Surface must be > 0")
        return v


class BuildingRoomModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.building

    create_dto = BuildingRoomHandlerCreate
    update_dto = BuildingRoomHandlerUpdate
    response_dto = BuildingRoomHandlerResponse

    kind_field: str = "building_name"
    subkind_field: str = "room_name"
    extra_factor_fields: list[str] = ["room_type"]
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
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "building_name": DataEntry.data["building_name"].as_string(),
        "room_name": DataEntry.data["room_name"].as_string(),
        "room_type": DataEntry.data["room_type"].as_string(),
    }

    async def resolve_primary_factor_id(
        self,
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        db: AsyncSession,
        existing_data: Optional[dict] = None,
    ) -> dict:
        payload["primary_factor_id"] = None
        return payload

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """Pre-compute per-subcategory kWh from kwh_per_m2 × surface."""
        surface = data_entry.data.get("room_surface_square_meter") or 0
        return {
            "lighting_kwh": (data_entry.data.get("lighting_kwh_per_square_meter") or 0)
            * surface,
            "cooling_kwh": (data_entry.data.get("cooling_kwh_per_square_meter") or 0)
            * surface,
            "ventilation_kwh": (
                data_entry.data.get("ventilation_kwh_per_square_meter") or 0
            )
            * surface,
            "heating_kwh": (data_entry.data.get("heating_kwh_per_square_meter") or 0)
            * surface,
        }

    # Maps each building EmissionType leaf → (factor subkind, context quantity_key)
    _EMISSION_TO_SUBCATEGORY: dict = {
        EmissionType.buildings__rooms__lighting: ("lighting", "lighting_kwh"),
        EmissionType.buildings__rooms__cooling: ("cooling", "cooling_kwh"),
        EmissionType.buildings__rooms__ventilation: ("ventilation", "ventilation_kwh"),
        EmissionType.buildings__rooms__heating_elec: ("heating_elec", "heating_kwh"),
        EmissionType.buildings__rooms__heating_thermal: (
            "heating_thermal",
            "heating_kwh",
        ),
    }

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        mapping = self._EMISSION_TO_SUBCATEGORY.get(emission_type)
        if not mapping:
            return []
        subkind, quantity_key = mapping
        building_name = data_entry.data.get("building_name", "")
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.building,
                    kind=building_name,
                    subkind=subkind,
                ),
                formula_key="ef_kg_co2eq_per_kwh",
                quantity_key=quantity_key,
                multiplier_key="conversion_factor",
                multiplier_default=1.0,
            )
        ]

    def to_response(self, data_entry: DataEntry) -> BuildingRoomHandlerResponse:
        d = data_entry.data
        pf = d.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
                "room_type": pf.get("kind") or d.get("room_type"),
                "heating_kwh_per_m2": pf.get("heating_kwh_per_m2"),
                "cooling_kwh_per_m2": pf.get("cooling_kwh_per_m2"),
                "ventilation_kwh_per_m2": pf.get("ventilation_kwh_per_m2"),
                "lighting_kwh_per_m2": pf.get("lighting_kwh_per_m2"),
                "heating_kwh": d.get("heating_kwh"),
                "cooling_kwh": d.get("cooling_kwh"),
                "ventilation_kwh": d.get("ventilation_kwh"),
                "lighting_kwh": d.get("lighting_kwh"),
            }
        )

    def validate_create(self, payload: dict) -> BuildingRoomHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> BuildingRoomHandlerUpdate:
        return self.update_dto.model_validate(payload)


class EnergyCombustionHandlerResponse(DataEntryResponseGen):
    heating_type: str
    unit: Optional[str] = None
    quantity: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class EnergyCombustionHandlerCreate(DataEntryCreate):
    heating_type: str
    quantity: float
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be > 0")
        return v


class EnergyCombustionHandlerUpdate(DataEntryUpdate):
    heating_type: Optional[str] = None
    quantity: Optional[float] = None
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Quantity must be > 0")
        return v


class EnergyCombustionModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.energy_combustion

    create_dto = EnergyCombustionHandlerCreate
    update_dto = EnergyCombustionHandlerUpdate
    response_dto = EnergyCombustionHandlerResponse

    kind_field: str = "heating_type"
    subkind_field: str | None = None
    require_subkind_for_factor = False

    sort_map = {
        "id": DataEntry.id,
        "heating_type": Factor.classification["kind"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "heating_type": Factor.classification["kind"].as_string(),
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
                factor_id=int(factor_id),
                formula_key="kg_co2eq_per_unit",
                quantity_key="quantity",
            )
        ]

    def to_response(self, data_entry: DataEntry) -> EnergyCombustionHandlerResponse:
        primary_factor = data_entry.data.get("primary_factor", {})
        factor_values = primary_factor.get("values", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "heating_type": primary_factor.get("kind")
                or data_entry.data.get("heating_type"),
                "unit": factor_values.get("unit") or data_entry.data.get("unit"),
            }
        )

    def validate_create(self, payload: dict) -> EnergyCombustionHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> EnergyCombustionHandlerUpdate:
        return self.update_dto.model_validate(payload)
