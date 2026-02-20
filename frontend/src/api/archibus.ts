import { api } from 'src/api/http';

export interface ArchibusBuilding {
  building_code: string;
  building_name: string;
}

export interface ArchibusRoom {
  building_code: string;
  building_name: string;
  room_code: string;
  room_name: string;
  generic_type_din: string;
  sia_type: string;
  surface_m2: number;
}

export async function getArchibusBuildings(): Promise<ArchibusBuilding[]> {
  return api.get('modules/archibus-rooms').json<ArchibusBuilding[]>();
}

export async function getArchibusRooms(
  buildingName: string,
): Promise<ArchibusRoom[]> {
  return api
    .get('modules/archibus-rooms', {
      searchParams: { building_name: buildingName },
    })
    .json<ArchibusRoom[]>();
}
