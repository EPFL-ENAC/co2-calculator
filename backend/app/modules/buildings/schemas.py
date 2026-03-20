from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
)

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
)
from app.models.factor import Factor
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
from app.services.building_room_service import BuildingRoomService


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


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
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


VALID_ROOM_TYPES: list[Optional[str]] = [
    "office",
    "miscellaneous",
    "laboratories",
    "archives",
    "libraries",
    "auditoriums",
    None,
]


class BuildingRoomHandlerCreate(DataEntryCreate):
    building_name: str
    room_name: str
    room_type: Optional[str] = None
    note: Optional[str] = None

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROOM_TYPES:
            raise ValueError(
                f"room_type must be one of: {[r for r in VALID_ROOM_TYPES if r]}"
            )
        return v


class BuildingRoomHandlerUpdate(DataEntryUpdate):
    building_name: Optional[str] = None
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    note: Optional[str] = None

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROOM_TYPES:
            raise ValueError(
                f"room_type must be one of: {[r for r in VALID_ROOM_TYPES if r]}"
            )
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

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    # Maps each building EmissionType leaf → factor field for kwh/m².
    _EMISSION_TO_KWH_FIELD: dict = {
        EmissionType.buildings__rooms__lighting: "lighting_kwh_per_square_meter",
        EmissionType.buildings__rooms__cooling: "cooling_kwh_per_square_meter",
        EmissionType.buildings__rooms__ventilation: "ventilation_kwh_per_square_meter",
        EmissionType.buildings__rooms__heating_elec: "heating_kwh_per_square_meter",
        EmissionType.buildings__rooms__heating_thermal: "heating_kwh_per_square_meter",
    }

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """call RoomService to get room surface by room_name"""
        room_name = data_entry.data.get("room_name")
        building_name = data_entry.data.get("building_name")
        if not room_name or not building_name:
            return {}
        service = BuildingRoomService(session)
        room = await service.get_room(room_name=room_name)
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
        kwh_per_m2 = factor_values.get(kwh_field)
        ef = factor_values.get("ef_kg_co2eq_per_kwh")
        if surface is None or kwh_per_m2 is None or ef is None:
            return None

        conversion_factor = factor_values.get("conversion_factor") or 1.0
        kwh = float(surface) * float(kwh_per_m2)
        return kwh * float(ef) * float(conversion_factor)

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:
        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        kwh_field = self._EMISSION_TO_KWH_FIELD.get(emission_type)
        if not kwh_field:
            return []

        def _building_formula(ctx: dict, factor_values: dict) -> float | None:
            return self._compute_kwh_emission(ctx, factor_values, kwh_field)

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_building_formula,
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
                "heating_kwh_per_square_meter": d.get("primary_factor", {}).get(
                    "heating_kwh_per_square_meter", None
                ),
                "cooling_kwh_per_square_meter": d.get("primary_factor", {}).get(
                    "cooling_kwh_per_square_meter", None
                ),
                "ventilation_kwh_per_square_meter": d.get("primary_factor", {}).get(
                    "ventilation_kwh_per_square_meter", None
                ),
                "lighting_kwh_per_square_meter": d.get("primary_factor", {}).get(
                    "lighting_kwh_per_square_meter", None
                ),
            }
        )

    def validate_create(self, payload: dict) -> BuildingRoomHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> BuildingRoomHandlerUpdate:
        return self.update_dto.model_validate(payload)


## BUILDINGS FACTOR HANDLER


## FACTORS for BUILDINGS

buildings_classification_fields: list[str] = [
    "building_name",
    "room_type",
    "energy_type",
]
buildings_value_fields: list[str] = [
    "ef_kg_co2eq_per_kwh",
    "heating_kwh_per_square_meter",
    "cooling_kwh_per_square_meter",
    "ventilation_kwh_per_square_meter",
    "lighting_kwh_per_square_meter",
    "conversion_factor",
]


class _BuildingsFactorValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_kwh",
        "heating_kwh_per_square_meter",
        "cooling_kwh_per_square_meter",
        "ventilation_kwh_per_square_meter",
        "lighting_kwh_per_square_meter",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        valid_room_types = [
            "office",
            "miscellaneous",
            "laboratories",
            "archives",
            "libraries",
            "auditoriums",
            None,
        ]
        if not v:
            raise ValueError("Room type is required")
        if v not in valid_room_types:
            raise ValueError("Invalid room type")
        return v

    @field_validator("energy_type", mode="after")
    @classmethod
    def validate_energy_type(cls, v: str) -> str:
        valid_energy_types = [
            "electric",
            "thermal",
            None,
        ]
        # Normalize aliases
        energy_type_aliases = {
            "electric": "electric",
            "elec": "electric",
            "electricity": "electric",
            "therm": "thermal",
        }
        normalized = energy_type_aliases.get(v.lower() if v else v, v)
        if not normalized:
            raise ValueError("Energy type is required")
        if normalized not in valid_energy_types:
            raise ValueError(
                f"Invalid energy type: {v}. Must be one of: electric, thermal"
            )
        return normalized

    # todo: if conversion_factor is None -> 1.0
    # but should we enforce it to be set explicitly in the factor?


class BuildingBaseFactor:
    building_name: str
    room_type: str
    heating_kwh_per_square_meter: float
    cooling_kwh_per_square_meter: float
    ventilation_kwh_per_square_meter: float
    lighting_kwh_per_square_meter: float
    ef_kg_co2eq_per_kwh: float
    energy_type: str
    conversion_factor: float


class BuildingsFactorCreate(
    _BuildingsFactorValidationMixin, FactorCreate, BuildingBaseFactor
):
    pass


class BuildingsFactorUpdate(
    _BuildingsFactorValidationMixin, FactorUpdate, BuildingBaseFactor
):
    pass


class BuildingsFactorResponse(FactorResponseGen, BuildingBaseFactor):
    pass


class BuildingsFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.building,
    ]
    emission_type: EmissionType = EmissionType.buildings__rooms

    create_dto = BuildingsFactorCreate
    update_dto = BuildingsFactorUpdate
    response_dto = BuildingsFactorResponse

    classification_fields: list[str] = buildings_classification_fields
    value_fields: list[str] = buildings_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)


### ENERGY COMBUSTION DATA_ENTRY_TYPE


class EnergyCombustionHandlerResponse(DataEntryResponseGen):
    name: str
    unit: Optional[str] = None
    quantity: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class EnergyCombustionHandlerCreate(DataEntryCreate):
    name: str
    quantity: float
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


class EnergyCombustionHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None
    quantity: Optional[float] = None
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


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
        "name": Factor.classification["name"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": Factor.classification["name"].as_string(),
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
        factor_values = primary_factor.get("values", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "name": primary_factor.get("kind") or data_entry.data.get("name"),
                "unit": factor_values.get("unit") or data_entry.data.get("unit"),
            }
        )

    def validate_create(self, payload: dict) -> EnergyCombustionHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> EnergyCombustionHandlerUpdate:
        return self.update_dto.model_validate(payload)


## ENERGY COMBUSTION FACTOR HANDLER


## FACTORS for energy combustion

energy_combustion_classification_fields: list[str] = ["unit", "name"]
energy_combustion_value_fields: list[str] = [
    "ef_kg_co2eq_per_unit",
]


class _EnergyCombustionFactorValidationMixin:
    @field_validator("ef_kg_co2eq_per_unit", mode="after")
    @classmethod
    def validate_factor_non_negative(
        cls, v: Optional[float], info: ValidationInfo
    ) -> Optional[float]:
        return _validate_non_negative_float(v, info.field_name or "")


class EnergyCombustionFactorCreate(
    _EnergyCombustionFactorValidationMixin, FactorCreate
):
    # data_entry_type: str #only for upload in datamanagement
    unit: str
    name: str
    ef_kg_co2eq_per_unit: float


class EnergyCombustionFactorUpdate(
    _EnergyCombustionFactorValidationMixin, FactorUpdate
):
    unit: Optional[str] = None
    name: Optional[str] = None
    ef_kg_co2eq_per_unit: Optional[float] = None


class EnergyCombustionFactorResponse(FactorResponseGen):
    unit: str
    name: str
    ef_kg_co2eq_per_unit: float


class EnergyCombustionFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.energy_combustion,
    ]
    emission_type: EmissionType = EmissionType.buildings__combustion

    create_dto = EnergyCombustionFactorCreate
    update_dto = EnergyCombustionFactorUpdate
    response_dto = EnergyCombustionFactorResponse

    classification_fields: list[str] = energy_combustion_classification_fields
    value_fields: list[str] = energy_combustion_value_fields

    def to_response(self, factor: Factor) -> FactorResponseGen:
        return self.response_dto.model_validate(factor.model_dump)
