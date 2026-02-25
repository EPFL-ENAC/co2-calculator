import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getArchibusBuildings,
  getArchibusRooms,
  type ArchibusBuilding,
  type ArchibusRoom,
} from 'src/api/archibus';

export const useArchibusRoomStore = defineStore('archibus', () => {
  const ONE_MINUTE_MS = 60_000;

  const buildingsByUnit = reactive<Record<string, ArchibusBuilding[]>>({});
  const buildingsFetchedAt = reactive<Record<string, number>>({});

  const roomsByUnitAndBuilding = reactive<Record<string, ArchibusRoom[]>>({});
  const roomsFetchedAt = reactive<Record<string, number>>({});

  async function fetchBuildings(unitId: number): Promise<ArchibusBuilding[]> {
    const cacheKey = String(unitId);
    const now = Date.now();
    const existing = buildingsByUnit[cacheKey];
    const last = buildingsFetchedAt[cacheKey];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const buildings = await getArchibusBuildings(unitId);
    buildingsByUnit[cacheKey] = buildings;
    buildingsFetchedAt[cacheKey] = now;
    return buildings;
  }

  async function fetchRooms(
    unitId: number,
    buildingName: string,
  ): Promise<ArchibusRoom[]> {
    const cacheKey = `${unitId}::${buildingName}`;
    const now = Date.now();
    const existing = roomsByUnitAndBuilding[cacheKey];
    const last = roomsFetchedAt[cacheKey];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const rooms = await getArchibusRooms(unitId, buildingName);
    roomsByUnitAndBuilding[cacheKey] = rooms;
    roomsFetchedAt[cacheKey] = now;
    return rooms;
  }

  return {
    buildingsByUnit,
    roomsByUnitAndBuilding,
    fetchBuildings,
    fetchRooms,
  };
});
