import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getClassificationTree,
  getPowerFactor,
  type OptionTree,
  type PowerFactorResponse,
} from 'src/api/powerFactors';
import {
  AllSubmoduleTypes,
  SUBMODULE_BUILDINGS_TYPES,
} from 'src/constant/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

type Option = { label: string; value: string };

export const useFactorsStore = defineStore('factors', () => {
  const ONE_MINUTE_MS = 60_000;
  const workspaceStore = useWorkspaceStore();

  const treeBySubmodule = reactive<
    Partial<Record<AllSubmoduleTypes, OptionTree>>
  >({});
  const treeFetchedAt = reactive<Partial<Record<AllSubmoduleTypes, number>>>(
    {},
  );
  const treeUnitId = reactive<Partial<Record<AllSubmoduleTypes, number>>>({});

  async function ensureTree(submodule: AllSubmoduleTypes): Promise<OptionTree> {
    const now = Date.now();
    const existing = treeBySubmodule[submodule];
    const last = treeFetchedAt[submodule];
    const currentUnitId = workspaceStore.selectedUnit?.id;
    const requestedUnitId =
      submodule === SUBMODULE_BUILDINGS_TYPES.Building ? currentUnitId : undefined;
    const cachedUnitId = treeUnitId[submodule];
    const hasCachedEntries = !!existing && Object.keys(existing).length > 0;

    if (
      hasCachedEntries &&
      last &&
      now - last < ONE_MINUTE_MS &&
      cachedUnitId === requestedUnitId
    ) {
      return existing;
    }

    const tree = await getClassificationTree(submodule, requestedUnitId);
    treeBySubmodule[submodule] = tree;
    treeFetchedAt[submodule] = now;
    treeUnitId[submodule] = requestedUnitId;
    return tree;
  }

  /**
   * Walk the cached tree along `path` and return sorted child keys as options.
   * Returns [] if any segment in the path is missing.
   */
  function getOptionsAtPath(
    submodule: AllSubmoduleTypes,
    path: string[],
  ): Option[] {
    let node: OptionTree | undefined = treeBySubmodule[submodule];
    for (const segment of path) {
      if (!node || !(segment in node)) return [];
      node = node[segment];
    }
    if (!node) return [];
    return Object.keys(node)
      .sort()
      .map((k) => ({ label: k, value: k }));
  }

  async function fetchPowerFactor(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
    subClass?: string | null,
  ): Promise<PowerFactorResponse | null> {
    return await getPowerFactor(submodule, equipmentClass, subClass);
  }

  return {
    treeBySubmodule,
    treeFetchedAt,
    treeUnitId,
    ensureTree,
    getOptionsAtPath,
    fetchPowerFactor,
  };
});
