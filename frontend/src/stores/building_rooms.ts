import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { getBuildingRooms, type BuildingRoom } from 'src/api/building_rooms';

export const useBuildingRoomStore = defineStore('building_rooms', () => {
  const ONE_MINUTE_MS = 60_000;

  const roomsByBuilding = reactive<Record<string, BuildingRoom[]>>({});
  const roomsFetchedAt = reactive<Record<string, number>>({});

  async function fetchRooms(buildingName: string): Promise<BuildingRoom[]> {
    const cacheKey = buildingName;
    const now = Date.now();
    const existing = roomsByBuilding[cacheKey];
    const last = roomsFetchedAt[cacheKey];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const rooms = await getBuildingRooms(buildingName);
    roomsByBuilding[cacheKey] = rooms;
    roomsFetchedAt[cacheKey] = now;
    return rooms;
  }

  return {
    roomsByBuilding,
    fetchRooms,
  };
});
