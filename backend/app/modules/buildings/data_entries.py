from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class BuildingRoomBuildingResponse(BaseModel):
    building_location: str
    building_name: str


class BuildingRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    building_location: str
    building_name: str
    room_name: str
    room_type: str | None
    room_surface_square_meter: float | None


class BuildingRoomEnergyDefaultsResponse(BaseModel):
    heating_kwh_per_square_meter: float | None = None
    cooling_kwh_per_square_meter: float | None = None
    ventilation_kwh_per_square_meter: float | None = None
    lighting_kwh_per_square_meter: float | None = None


class BuildingRoomHandlerResponse(DataEntryResponseGen):
    building_name: str
    room_name: str | None = None
    room_type: str | None = None
    room_surface_square_meter: float | None = None
    room_allocation_ratio: float | None = None
    heating_kwh_per_square_meter: float | None = None
    cooling_kwh_per_square_meter: float | None = None
    ventilation_kwh_per_square_meter: float | None = None
    lighting_kwh_per_square_meter: float | None = None
    note: str | None = None
    kg_co2eq: float | None = None


VALID_ROOM_TYPES: list[str | None] = [
    "office",
    "miscellaneous",
    "laboratories",
    "archives",
    "libraries",
    "auditoriums",
    None,
]


class DiscardClientSurfaceMixin:
    """The room surface is resolved from the ``BuildingRoom`` reference
    table (read enrichment, ``pre_compute``, embodied-energy derivation) —
    a client-sent value is display-only and must never be persisted.
    """

    if TYPE_CHECKING:
        data: dict

    @model_validator(mode="after")
    def discard_client_surface(self):
        self.data.pop("room_surface_square_meter", None)
        return self


class BuildingRoomHandlerCreate(DiscardClientSurfaceMixin, DataEntryCreate):
    building_name: str
    room_name: str
    room_type: str
    room_allocation_ratio: float | None = None
    note: str | None = None

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        valid = [r for r in VALID_ROOM_TYPES if r]
        if v not in valid:
            raise ValueError(f"room_type must be one of: {valid}")
        return v

    @field_validator("room_allocation_ratio", mode="after")
    @classmethod
    def validate_room_allocation_ratio(cls, v: float | None) -> float | None:
        if v is not None and (v < 0 or v > 1):
            raise ValueError("room_allocation_ratio must be between 0 and 1")
        return v


class BuildingRoomHandlerUpdate(DiscardClientSurfaceMixin, DataEntryUpdate):
    building_name: str | None = None
    room_name: str | None = None
    room_type: str | None = None
    room_allocation_ratio: float | None = None
    note: str | None = None

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ROOM_TYPES:
            raise ValueError(
                f"room_type must be one of: {[r for r in VALID_ROOM_TYPES if r]}"
            )
        return v

    @field_validator("room_allocation_ratio", mode="after")
    @classmethod
    def validate_room_allocation_ratio(cls, v: float | None) -> float | None:
        if v is not None and (v < 0 or v > 1):
            raise ValueError("room_allocation_ratio must be between 0 and 1")
        return v


class EnergyCombustionHandlerResponse(DataEntryResponseGen):
    name: str
    unit: str | None = None
    quantity: float
    note: str | None = None
    kg_co2eq: float | None = None


class EnergyCombustionHandlerCreate(DataEntryCreate):
    name: str
    quantity: float
    note: str | None = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


class EnergyCombustionHandlerUpdate(DataEntryUpdate):
    name: str | None = None
    quantity: float | None = None
    note: str | None = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


class DiscardClientBuildingFieldsMixin(DiscardClientSurfaceMixin):
    """Embodied-energy rows persist only ``room_name`` — building_name (like
    the surface) resolves from the ``BuildingRoom`` reference table, so a
    client-sent value must never be persisted.
    """

    @model_validator(mode="after")
    def discard_client_building_name(self):
        self.data.pop("building_name", None)
        return self


class BuildingEmbodiedEnergyHandlerResponse(DataEntryResponseGen):
    room_name: str
    building_name: str | None = None
    room_surface_square_meter: float | None = None


class BuildingEmbodiedEnergyHandlerCreate(
    DiscardClientBuildingFieldsMixin, DataEntryCreate
):
    room_name: str


class BuildingEmbodiedEnergyHandlerUpdate(
    DiscardClientBuildingFieldsMixin, DataEntryUpdate
):
    room_name: str | None = None
