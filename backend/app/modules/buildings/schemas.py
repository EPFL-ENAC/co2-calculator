from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
    HeatingEnergyType,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.services.factor_service import FactorService


class BuildingRoomBuildingResponse(BaseModel):
    building_location: str
    building_name: str


class BuildingRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    building_location: str
    building_name: str
    room_name: str
    room_type: Optional[str]
    room_surface_square_meter: Optional[float]


class BuildingRoomEnergyDefaultsResponse(BaseModel):
    heating_kwh_per_square_meter: Optional[float] = None
    cooling_kwh_per_square_meter: Optional[float] = None
    ventilation_kwh_per_square_meter: Optional[float] = None
    lighting_kwh_per_square_meter: Optional[float] = None


class BuildingRoomHandlerResponse(DataEntryResponseGen):
    building_name: str
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    room_surface_square_meter: Optional[float] = None
    heating_kwh_per_square_meter: Optional[float] = None
    cooling_kwh_per_square_meter: Optional[float] = None
    ventilation_kwh_per_square_meter: Optional[float] = None
    lighting_kwh_per_square_meter: Optional[float] = None
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
        merged_payload = payload.copy()
        if existing_data:
            for key, value in existing_data.items():
                if key not in merged_payload:
                    merged_payload[key] = value

        building_name = (merged_payload.get("building_name") or "").strip()
        room_type = (merged_payload.get("room_type") or "").strip().lower()

        if building_name and room_type:
            stmt = (
                select(Factor)
                .where(
                    col(Factor.data_entry_type_id) == DataEntryTypeEnum.building.value,
                    Factor.classification["kind"].as_string() == building_name,
                    Factor.classification["subkind"].as_string() == room_type,
                )
                .order_by(col(Factor.id).asc())
            )
            factor = (await db.exec(stmt)).first()
            if factor:
                values = factor.values or {}
                payload["heating_kwh_per_square_meter"] = values.get(
                    "heating_kwh_per_square_meter"
                )
                payload["cooling_kwh_per_square_meter"] = values.get(
                    "cooling_kwh_per_square_meter"
                )
                payload["ventilation_kwh_per_square_meter"] = values.get(
                    "ventilation_kwh_per_square_meter"
                )
                payload["lighting_kwh_per_square_meter"] = values.get(
                    "lighting_kwh_per_square_meter"
                )
                payload["primary_factor_id"] = factor.id
            else:
                payload["primary_factor_id"] = None
        else:
            payload["primary_factor_id"] = None

        self._set_energy_intermediates(payload, {**merged_payload, **payload})
        return payload

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _set_energy_intermediates(self, payload: dict, merged_payload: dict) -> None:
        """Persist derived kWh values in entry payload for traceability/UI use."""
        surface = self._safe_float(merged_payload.get("room_surface_square_meter"))
        payload["heating_kwh"] = (
            self._safe_float(merged_payload.get("heating_kwh_per_square_meter"))
            * surface
        )
        payload["cooling_kwh"] = (
            self._safe_float(merged_payload.get("cooling_kwh_per_square_meter"))
            * surface
        )
        payload["ventilation_kwh"] = (
            self._safe_float(merged_payload.get("ventilation_kwh_per_square_meter"))
            * surface
        )
        payload["lighting_kwh"] = (
            self._safe_float(merged_payload.get("lighting_kwh_per_square_meter"))
            * surface
        )

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """Pre-compute per-subcategory kWh from * kwh_per_square_meter × surface."""
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

    # Maps each building EmissionType leaf → context quantity_key.
    _EMISSION_TO_QUANTITY: dict = {
        EmissionType.buildings__rooms__lighting: "lighting_kwh",
        EmissionType.buildings__rooms__cooling: "cooling_kwh",
        EmissionType.buildings__rooms__ventilation: "ventilation_kwh",
        EmissionType.buildings__rooms__heating_elec: "heating_kwh",
        EmissionType.buildings__rooms__heating_thermal: "heating_kwh",
    }

    @staticmethod
    def _compute_kwh_emission(
        ctx: dict,
        factor_values: dict,
        quantity_key: str,
        expected_energy_type: HeatingEnergyType | None = None,
    ) -> float | None:
        quantity = ctx.get(quantity_key)
        ef = factor_values.get("ef_kg_co2eq_per_kwh")
        if quantity is None or ef is None:
            return None

        if expected_energy_type is not None:
            energy_type = (factor_values.get("energy_type") or "").strip().lower()
            if energy_type != expected_energy_type.value:
                return None

        conversion_factor = factor_values.get("conversion_factor") or 1.0
        return float(quantity) * float(ef) * float(conversion_factor)

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        quantity_key = self._EMISSION_TO_QUANTITY.get(emission_type)
        if not quantity_key:
            return []
        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []
        expected_energy_type: HeatingEnergyType | None = None
        if emission_type == EmissionType.buildings__rooms__heating_elec:
            expected_energy_type = HeatingEnergyType.elec
        elif emission_type == EmissionType.buildings__rooms__heating_thermal:
            expected_energy_type = HeatingEnergyType.thermal

        formula_func = None
        if expected_energy_type is not None:

            def _heating_formula(local_ctx: dict, factor_values: dict) -> float | None:
                return self._compute_kwh_emission(
                    local_ctx,
                    factor_values,
                    quantity_key,
                    expected_energy_type,
                )

            formula_func = _heating_formula

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_key="" if formula_func else "ef_kg_co2eq_per_kwh",
                quantity_key=quantity_key,
                multiplier_key=None if formula_func else "conversion_factor",
                multiplier_default=1.0,
                formula_func=formula_func,
            )
        ]

    def to_response(self, data_entry: DataEntry) -> BuildingRoomHandlerResponse:
        d = data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
                "room_type": d.get("room_type"),
                "heating_kwh_per_square_meter": d.get("heating_kwh_per_square_meter"),
                "cooling_kwh_per_square_meter": d.get("cooling_kwh_per_square_meter"),
                "ventilation_kwh_per_square_meter": d.get(
                    "ventilation_kwh_per_square_meter"
                ),
                "lighting_kwh_per_square_meter": d.get("lighting_kwh_per_square_meter"),
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

    async def resolve_primary_factor_id(
        self,
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        db: AsyncSession,
        existing_data: Optional[dict] = None,
    ) -> dict:
        data = payload.copy()
        if existing_data:
            for key, value in existing_data.items():
                if key not in data:
                    data[key] = value
        kind = data.get("heating_type", "")
        factor_service = FactorService(db)
        factor = await factor_service.get_by_classification(
            data_entry_type=data_entry_type_id, kind=kind
        )
        payload["primary_factor_id"] = factor.id if factor else None
        return payload

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
