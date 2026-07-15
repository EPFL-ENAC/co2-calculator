from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

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
    room_allocation_ratio: Optional[float] = None
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
    room_type: str
    room_allocation_ratio: Optional[float] = None
    note: Optional[str] = None

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        valid = [r for r in VALID_ROOM_TYPES if r]
        if v not in valid:
            raise ValueError(f"room_type must be one of: {valid}")
        return v

    @field_validator("room_allocation_ratio", mode="after")
    @classmethod
    def validate_room_allocation_ratio(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 1):
            raise ValueError("room_allocation_ratio must be between 0 and 1")
        return v


class BuildingRoomHandlerUpdate(DataEntryUpdate):
    building_name: Optional[str] = None
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    room_allocation_ratio: Optional[float] = None
    note: Optional[str] = None

    @field_validator("room_type", mode="after")
    @classmethod
    def validate_room_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROOM_TYPES:
            raise ValueError(
                f"room_type must be one of: {[r for r in VALID_ROOM_TYPES if r]}"
            )
        return v

    @field_validator("room_allocation_ratio", mode="after")
    @classmethod
    def validate_room_allocation_ratio(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 1):
            raise ValueError("room_allocation_ratio must be between 0 and 1")
        return v


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


class BuildingEmbodiedEnergyHandlerResponse(DataEntryResponseGen):
    building_name: str


class BuildingEmbodiedEnergyHandlerCreate(DataEntryCreate):
    building_name: str


class BuildingEmbodiedEnergyHandlerUpdate(DataEntryUpdate):
    building_name: Optional[str] = None
