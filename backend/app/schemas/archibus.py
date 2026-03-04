"""Archibus API response schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ArchibusBuildingResponse(BaseModel):
    building_location: str
    building_name: str


class ArchibusRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_institutional_id: Optional[str] = None
    building_location: str
    building_name: str
    room_name: str
    room_type: Optional[str]
    room_surface_square_meter: Optional[float]
    heating_kwh_per_square_meter: Optional[float]
    cooling_kwh_per_square_meter: Optional[float]
    ventilation_kwh_per_square_meter: Optional[float]
    lighting_kwh_per_square_meter: Optional[float]
