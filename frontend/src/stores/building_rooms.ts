import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { getBuildingRooms, type BuildingRoomInfo } from 'src/api/building_rooms';

export const useBuildingRoomStore = defineStore('building_rooms', () => {
  const ONE_MINUTE_MS = 60_000;

  const roomsByUnitAndBuilding = reactive<Record<string, BuildingRoomInfo[]>>(
    {},
  );
  const roomsFetchedAt = reactive<Record<string, number>>({});

  async function fetchRooms(
    unitId: number,
    buildingName: string,
  ): Promise<BuildingRoomInfo[]> {
    const cacheKey = `${unitId}::${buildingName}`;
    const now = Date.now();
    const existing = roomsByUnitAndBuilding[cacheKey];
    const last = roomsFetchedAt[cacheKey];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const rooms = await getBuildingRooms(unitId, buildingName);
    roomsByUnitAndBuilding[cacheKey] = rooms;
    roomsFetchedAt[cacheKey] = now;
    return rooms;
  }

  return {
    roomsByUnitAndBuilding,
    fetchRooms,
  };
});
