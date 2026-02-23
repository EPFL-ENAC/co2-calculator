import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getSubclassMap,
  getFactorValues,
  ValueFactorResponse,
} from 'src/api/factors';
import { AllSubmoduleTypes, enumSubmodule } from 'src/constant/modules';

type Option = { label: string; value: string };

export const useFactorsStore = defineStore('factors', () => {
  const ONE_MINUTE_MS = 60_000;

  const treeBySubmodule = reactive<
    Partial<Record<AllSubmoduleTypes, OptionTree>>
  >({});
  const treeFetchedAt = reactive<Partial<Record<AllSubmoduleTypes, number>>>(
    {},
  );

  async function ensureSubclassOptionMap(
    submodule: keyof typeof enumSubmodule,
  ): Promise<Record<string, Option[]>> {
    const now = Date.now();
    const existing = treeBySubmodule[submodule];
    const last = treeFetchedAt[submodule];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const tree = await getClassificationTree(submodule);
    treeBySubmodule[submodule] = tree;
    treeFetchedAt[submodule] = now;
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
  ): Promise<ValueFactorResponse | null> {
    return await getFactorValues(submodule, equipmentClass, subClass);
  }

  return {
    treeBySubmodule,
    treeFetchedAt,
    ensureTree,
    getOptionsAtPath,
    fetchPowerFactor,
  };
});
