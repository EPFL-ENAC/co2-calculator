from typing import Any, Optional

from pydantic import field_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.building_room import BuildingRoom
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
    FactorQuery,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.taxonomy import TaxonomyNode
from app.repositories.building_room_repo import BuildingRoomRepository
from app.repositories.factor_repo import FactorRepository
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
    heating_kwh: Optional[float] = None
    cooling_kwh: Optional[float] = None
    ventilation_kwh: Optional[float] = None
    lighting_kwh: Optional[float] = None
    kg_co2eq: Optional[float] = None


class BuildingRoomHandlerCreate(DataEntryCreate):
    building_name: str
    room_name: str
    room_type: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None

    @field_validator("kg_co2eq", mode="after")
    @classmethod
    def validate_kg_co2eq(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("kg_co2eq must be >= 0")
        return v


class BuildingRoomHandlerUpdate(DataEntryUpdate):
    building_name: Optional[str] = None
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None

    @field_validator("kg_co2eq", mode="after")
    @classmethod
    def validate_kg_co2eq(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("kg_co2eq must be >= 0")
        return v


# Category → (emission_type, energy_type) mapping
_EMISSION_TYPE_TO_CATEGORY: dict[EmissionType, tuple[str, str]] = {
    EmissionType.buildings__rooms__lighting: ("lighting", "elec"),
    EmissionType.buildings__rooms__cooling: ("cooling", "elec"),
    EmissionType.buildings__rooms__ventilation: ("ventilation", "elec"),
    EmissionType.buildings__rooms__heating_elec: ("heating", "elec"),
    EmissionType.buildings__rooms__heating_thermal: ("heating", "thermal"),
}


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

        building_name = (payload.get("building_name") or "").strip()
        room_name = (payload.get("room_name") or "").strip()
        if not building_name or not room_name:
            return payload

        # Resolve authoritative surface + room_type from the reference table
        room = await BuildingRoomRepository(db).get_room_by_names(
            building_name, room_name
        )
        surface = None
        room_type = (payload.get("room_type") or "").strip() or None
        if room is not None:
            if room.room_surface_square_meter is not None:
                surface = room.room_surface_square_meter
                payload["room_surface_square_meter"] = surface
            if room.room_type:
                room_type = room.room_type
                payload["room_type"] = room_type

        if surface is None or not room_type:
            return payload

        # Fetch energy factors and compute kWh per category
        factor_repo = FactorRepository(db)
        categories = [
            ("heating", "elec"),
            ("heating", "thermal"),
            ("cooling", "elec"),
            ("ventilation", "elec"),
            ("lighting", "elec"),
        ]
        heating_kwh: Optional[float] = None
        cooling_kwh: Optional[float] = None
        ventilation_kwh: Optional[float] = None
        lighting_kwh: Optional[float] = None

        for category, energy_type in categories:
            factor = await factor_repo.get_factor(
                DataEntryTypeEnum.building,
                subkind=category,
                room_type=room_type,
                energy_type=energy_type,
            )
            if factor is None:
                continue
            fv = factor.values or {}
            kwh_per_m2 = fv.get(f"{category}_kwh_per_square_meter")
            if kwh_per_m2 is None:
                continue
            computed = surface * kwh_per_m2

            if category == "cooling":
                cooling_kwh = computed
            elif category == "ventilation":
                ventilation_kwh = computed
            elif category == "lighting":
                lighting_kwh = computed
            elif category == "heating":
                # Use first heating factor found (elec takes priority, then thermal)
                if heating_kwh is None:
                    heating_kwh = computed

        if heating_kwh is not None:
            payload["heating_kwh"] = heating_kwh
        if cooling_kwh is not None:
            payload["cooling_kwh"] = cooling_kwh
        if ventilation_kwh is not None:
            payload["ventilation_kwh"] = ventilation_kwh
        if lighting_kwh is not None:
            payload["lighting_kwh"] = lighting_kwh

        return payload

    async def pre_compute(
        self,
        data_entry: Any,
        session: AsyncSession,
    ) -> dict:
        building_name = data_entry.data.get("building_name")
        room_name = data_entry.data.get("room_name")
        if not building_name or not room_name:
            return {}
        room = await BuildingRoomRepository(session).get_room_by_names(
            building_name, room_name
        )
        if room is None:
            return {}
        result: dict = {}
        if room.room_surface_square_meter is not None:
            result["room_surface_square_meter"] = room.room_surface_square_meter
        if room.room_type:
            result["room_type"] = room.room_type  # reference overrides user input
        return result

    def resolve_computations(
        self,
        data_entry: Any,
        emission_type: Any,
        ctx: dict,
    ) -> list:
        # If custom kg_co2eq provided → aggregate single row
        if ctx.get("kg_co2eq") is not None:
            if emission_type == EmissionType.buildings__rooms:
                return [
                    EmissionComputation(
                        emission_type=emission_type,
                        formula_func=lambda c, _fv: c.get("kg_co2eq"),
                    )
                ]
            return []

        if emission_type not in _EMISSION_TYPE_TO_CATEGORY:
            return []

        category, energy_type = _EMISSION_TYPE_TO_CATEGORY[emission_type]
        room_type = ctx.get("room_type")
        surface = ctx.get("room_surface_square_meter")
        if not surface:
            return []

        def formula(c: dict, fv: dict) -> Optional[float]:
            s = c.get("room_surface_square_meter")
            kwh_key = f"{category}_kwh_per_square_meter"
            kwh = fv.get(kwh_key)
            ef = fv.get("ef_kg_co2eq_per_kwh")
            conv = fv.get("conversion_factor") or 1.0
            if s is None or kwh is None or ef is None:
                return None
            return s * kwh * ef * conv

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.building,
                    subkind=category,
                    context={"room_type": room_type, "energy_type": energy_type},
                ),
                formula_func=formula,
            )
        ]

    async def get_taxonomy(
        self,
        data_entry_type: DataEntryTypeEnum,
        db: AsyncSession,
        unit_id: int | None = None,
    ) -> TaxonomyNode:
        """Build building/room taxonomy from the global building room reference."""
        rooms = await BuildingRoomRepository(db).list_rooms()
        by_building: dict[str, set[str]] = {}
        for room in rooms:
            if not isinstance(room, BuildingRoom):
                continue
            building_name = (room.building_name or "").strip()
            room_name = (room.room_name or "").strip()
            if not building_name:
                continue
            if building_name not in by_building:
                by_building[building_name] = set()
            if room_name:
                by_building[building_name].add(room_name)

        children: list[TaxonomyNode] = []
        for building_name in sorted(by_building.keys()):
            room_children = [
                TaxonomyNode(name=room_name, label=room_name)
                for room_name in sorted(by_building[building_name])
            ]
            children.append(
                TaxonomyNode(
                    name=building_name,
                    label=building_name,
                    children=room_children,
                )
            )

        return TaxonomyNode(
            name=data_entry_type.name,
            label=self.to_label(data_entry_type.name),
            children=children,
        )

    def to_response(self, data_entry: DataEntry) -> BuildingRoomHandlerResponse:
        d = data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **d,
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
    name: str
    unit: str
    quantity: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class EnergyCombustionHandlerCreate(DataEntryCreate):
    name: str
    unit: str
    quantity: float
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be > 0")
        return v


class EnergyCombustionHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None
    unit: Optional[str] = None
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

    kind_field: str = "name"
    subkind_field: str = "unit"
    require_subkind_for_factor = True

    sort_map = {
        "id": DataEntry.id,
        "name": Factor.classification["kind"].as_string(),
        "unit": Factor.classification["subkind"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": Factor.classification["kind"].as_string(),
        "unit": Factor.classification["subkind"].as_string(),
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
                formula_key="ef_kg_co2eq_per_unit",
                quantity_key="quantity",
            )
        ]

    def to_response(self, data_entry: DataEntry) -> EnergyCombustionHandlerResponse:
        primary_factor = data_entry.data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "name": primary_factor.get("kind") or data_entry.data.get("name"),
                "unit": primary_factor.get("subkind") or data_entry.data.get("unit"),
            }
        )

    def validate_create(self, payload: dict) -> EnergyCombustionHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> EnergyCombustionHandlerUpdate:
        return self.update_dto.model_validate(payload)
