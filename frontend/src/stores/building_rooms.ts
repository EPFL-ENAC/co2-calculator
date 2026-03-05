import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getBuildingRooms,
  getEnergyDefaults,
  type BuildingRoom,
  type BuildingRoomEnergyDefaults,
} from 'src/api/building_rooms';

export const useBuildingRoomStore = defineStore('building_rooms', () => {
  const ONE_MINUTE_MS = 60_000;

  const roomsByBuilding = reactive<Record<string, BuildingRoom[]>>({});
  const roomsFetchedAt = reactive<Record<string, number>>({});

  const energyDefaultsByKey = reactive<
    Record<string, BuildingRoomEnergyDefaults>
  >({});
  const energyDefaultsFetchedAt = reactive<Record<string, number>>({});

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

  async function fetchEnergyDefaults(
    buildingName: string,
    roomType: string,
  ): Promise<BuildingRoomEnergyDefaults> {
    const cacheKey = `${buildingName}__${roomType}`;
    const now = Date.now();
    const existing = energyDefaultsByKey[cacheKey];
    const last = energyDefaultsFetchedAt[cacheKey];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const defaults = await getEnergyDefaults(buildingName, roomType);
    energyDefaultsByKey[cacheKey] = defaults;
    energyDefaultsFetchedAt[cacheKey] = now;
    return defaults;
  }

  return {
    roomsByBuilding,
    fetchRooms,
    fetchEnergyDefaults,
  };
});
