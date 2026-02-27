import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getSubclassMap,
  getFactorValues,
  type ValueFactorResponse,
} from 'src/api/factors';
import {
  type AllSubmoduleTypes,
  enumSubmodule,
  SUBMODULE_BUILDINGS_TYPES,
} from 'src/constant/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

type Option = { label: string; value: string };

export const useFactorsStore = defineStore('factors', () => {
  const ONE_MINUTE_MS = 60_000;
  const workspaceStore = useWorkspaceStore();

  const subclassMapBySubmodule = reactive<
    Partial<Record<AllSubmoduleTypes, Record<string, string[]>>>
  >({});
  const subclassMapFetchedAt = reactive<
    Partial<Record<AllSubmoduleTypes, number>>
  >(
    {},
  );
  const subclassMapUnitId = reactive<Partial<Record<AllSubmoduleTypes, number>>>(
    {},
  );

  async function ensureTree(
    submodule: keyof typeof enumSubmodule,
  ): Promise<Record<string, string[]>> {
    const now = Date.now();
    const existing = subclassMapBySubmodule[submodule];
    const last = subclassMapFetchedAt[submodule];
    const currentUnitId = workspaceStore.selectedUnit?.id;
    const requestedUnitId =
      submodule === SUBMODULE_BUILDINGS_TYPES.Building ? currentUnitId : undefined;
    const cachedUnitId = subclassMapUnitId[submodule];
    const hasCachedEntries = !!existing && Object.keys(existing).length > 0;

    if (
      hasCachedEntries &&
      last &&
      now - last < ONE_MINUTE_MS &&
      cachedUnitId === requestedUnitId
    ) {
      return existing as Record<string, string[]>;
    }

    const subclassMap = await getSubclassMap(submodule, requestedUnitId);
    subclassMapBySubmodule[submodule] = subclassMap;
    subclassMapFetchedAt[submodule] = now;
    subclassMapUnitId[submodule] = requestedUnitId;
    return subclassMap;
  }

  /**
   * Return options from class/subclass map:
   * - [] path -> kind options
   * - [kind] path -> subkind options
   * - deeper path -> []
   */
  function getOptionsAtPath(
    submodule: AllSubmoduleTypes,
    path: string[],
  ): Option[] {
    const map = subclassMapBySubmodule[submodule];
    if (!map) return [];

    if (path.length === 0) {
      return Object.keys(map)
        .sort()
        .map((k) => ({ label: k, value: k }));
    }

    if (path.length === 1) {
      return (map[path[0]] ?? [])
        .slice()
        .sort()
        .map((k) => ({ label: k, value: k }));
    }

    return [];
  }

  async function fetchClassOptions(submodule: AllSubmoduleTypes): Promise<Option[]> {
    await ensureTree(submodule);
    return getOptionsAtPath(submodule, []);
  }

  async function fetchSubclassOptions(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
  ): Promise<Option[]> {
    await ensureTree(submodule);
    return getOptionsAtPath(submodule, [equipmentClass]);
  }

  async function fetchPowerFactor(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
    subClass?: string | null,
  ): Promise<ValueFactorResponse | null> {
    return await getFactorValues(submodule, equipmentClass, subClass);
  }

  return {
    subclassMapBySubmodule,
    subclassMapFetchedAt,
    subclassMapUnitId,
    ensureTree,
    getOptionsAtPath,
    fetchClassOptions,
    fetchSubclassOptions,
    fetchPowerFactor,
  };
});
