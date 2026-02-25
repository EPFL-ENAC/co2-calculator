import { api } from 'src/api/http';

export interface ArchibusBuilding {
  building_location: string;
  building_name: string;
}

export interface ArchibusRoom {
  unit_institutional_id: string | null;
  building_location: string;
  building_name: string;
  room_name: string;
  room_type: string | null;
  room_surface_square_meter: number | null;
  heating_kwh_per_square_meter: number | null;
  cooling_kwh_per_square_meter: number | null;
  ventilation_kwh_per_square_meter: number | null;
  lighting_kwh_per_square_meter: number | null;
}

export async function getArchibusBuildings(
  unitId: number,
): Promise<ArchibusBuilding[]> {
  return api
    .get('modules/archibus-rooms', {
      searchParams: { unit_id: unitId },
    })
    .json<ArchibusBuilding[]>();
}

export async function getArchibusRooms(
  unitId: number,
  buildingName: string,
): Promise<ArchibusRoom[]> {
  return api
    .get('modules/archibus-rooms', {
      searchParams: { unit_id: unitId, building_name: buildingName },
    })
    .json<ArchibusRoom[]>();
}
