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
