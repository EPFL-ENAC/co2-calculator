"""Building rooms lookup API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_active_user
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import HeatingEnergyType
from app.models.user import User
from app.modules.buildings.schemas import (
    BuildingRoomBuildingResponse,
    BuildingRoomEnergyDefaultsResponse,
    BuildingRoomResponse,
)
from app.services.building_room_service import BuildingRoomService
from app.services.factor_service import FactorService

router = APIRouter()


@router.get(
    "/building-rooms/energy-defaults",
    response_model=BuildingRoomEnergyDefaultsResponse,
)
async def get_building_room_energy_defaults(
    building_name: str = Query(...),
    room_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> BuildingRoomEnergyDefaultsResponse:
    """Return per-category kWh/m² defaults for a given building and room type."""
    categories = ("heating", "cooling", "ventilation", "lighting")
    factor_service = FactorService(db)
    normalized_building = building_name.strip()
    normalized_room_type = room_type.strip().lower()

    def _kwh(factor) -> Optional[float]:
        if not factor:
            return None
        return (factor.values or {}).get("category_kwh_per_square_meter")

    result: dict[str, Optional[float]] = {}
    for category in categories:
        selected = None
        if category == "heating":
            elec_factor = await factor_service.get_factor(
                data_entry_type=DataEntryTypeEnum.building,
                kind=normalized_building,
                room_type=normalized_room_type,
                subkind="heating",
                energy_type=HeatingEnergyType.elec.value,
            )
            thermal_factor = await factor_service.get_factor(
                data_entry_type=DataEntryTypeEnum.building,
                kind=normalized_building,
                room_type=normalized_room_type,
                subkind="heating",
                energy_type=HeatingEnergyType.thermal.value,
            )
            # Backward compatibility for old heating factors without energy_type.
            legacy_factor = await factor_service.get_factor(
                data_entry_type=DataEntryTypeEnum.building,
                kind=normalized_building,
                room_type=normalized_room_type,
                subkind="heating",
            )
            selected = elec_factor or thermal_factor or legacy_factor
        else:
            selected = await factor_service.get_factor(
                data_entry_type=DataEntryTypeEnum.building,
                kind=normalized_building,
                room_type=normalized_room_type,
                subkind=category,
            )

        result[f"{category}_kwh_per_square_meter"] = _kwh(selected)
    return BuildingRoomEnergyDefaultsResponse(**result)


@router.get(
    "/building-rooms",
    response_model=list[BuildingRoomBuildingResponse | BuildingRoomResponse],
)
async def get_building_rooms(
    building_location: Optional[str] = Query(default=None),
    building_name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> list[BuildingRoomBuildingResponse | BuildingRoomResponse]:
    """Return buildings and rooms for the Buildings module dropdowns."""

    building_room_service = BuildingRoomService(db)

    if building_location or building_name:
        rooms = await building_room_service.list_rooms(
            building_location=building_location,
            building_name=building_name,
        )
        return [BuildingRoomResponse.model_validate(room) for room in rooms]

    buildings = await building_room_service.list_buildings()
    return [
        BuildingRoomBuildingResponse.model_validate(building) for building in buildings
    ]
