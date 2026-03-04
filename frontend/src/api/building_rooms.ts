import { api } from 'src/api/http';

export interface BuildingInfo {
  building_location: string;
  building_name: string;
}

export interface BuildingRoomInfo {
  building_location: string;
  building_name: string;
  room_name: string;
  room_type: string | null;
  room_surface_square_meter: number | null;
}

export async function getBuildings(unitId: number): Promise<BuildingInfo[]> {
  return api
    .get('modules/building-rooms', {
      searchParams: { unit_id: unitId },
    })
    .json<BuildingInfo[]>();
}

export async function getBuildingRooms(
  unitId: number,
  buildingName: string,
): Promise<BuildingRoomInfo[]> {
  return api
    .get('modules/building-rooms', {
      searchParams: { unit_id: unitId, building_name: buildingName },
    })
    .json<BuildingRoomInfo[]>();
}
