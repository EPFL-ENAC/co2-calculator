import { api } from 'src/api/http';

export interface BuildingRoomBuilding {
  building_location: string;
  building_name: string;
}

export interface BuildingRoom {
  building_location: string;
  building_name: string;
  room_name: string;
  room_type: string | null;
  room_surface_square_meter: number | null;
}

export interface BuildingRoomEnergyDefaults {
  heating_kwh_per_square_meter: number | null;
  cooling_kwh_per_square_meter: number | null;
  ventilation_kwh_per_square_meter: number | null;
  lighting_kwh_per_square_meter: number | null;
}

export async function getBuildingRoomBuildings(): Promise<
  BuildingRoomBuilding[]
> {
  return api.get('modules/building-rooms').json<BuildingRoomBuilding[]>();
}

export async function getBuildingRooms(
  buildingName: string,
): Promise<BuildingRoom[]> {
  return api
    .get('modules/building-rooms', {
      searchParams: { building_name: buildingName },
    })
    .json<BuildingRoom[]>();
}

export async function getEnergyDefaults(
  buildingName: string,
  roomType: string,
): Promise<BuildingRoomEnergyDefaults> {
  return api
    .get('modules/building-rooms/energy-defaults', {
      searchParams: { building_name: buildingName, room_type: roomType },
    })
    .json<BuildingRoomEnergyDefaults>();
}
