import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { getArchibusRooms, type ArchibusRoom } from 'src/api/archibus';

export const useArchibusRoomStore = defineStore('archibus', () => {
  const ONE_MINUTE_MS = 60_000;

  const roomsByUnitAndBuilding = reactive<Record<string, ArchibusRoom[]>>({});
  const roomsFetchedAt = reactive<Record<string, number>>({});

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
    roomsByUnitAndBuilding,
    fetchRooms,
  };
});
