import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getSubclassMap,
  getFactorValues,
  type ValueFactorResponse,
} from 'src/api/factors';
import { type AllSubmoduleTypes, enumSubmodule } from 'src/constant/modules';

type Option = { label: string; value: string };

export const useFactorsStore = defineStore('factors', () => {
  const ONE_MINUTE_MS = 60_000;

  const subclassOptionMapBySubmodule = reactive<
    Partial<Record<AllSubmoduleTypes, Record<string, Option[]>>>
  >({});
  const subclassMapFetchedAt = reactive<
    Partial<Record<AllSubmoduleTypes, number>>
  >({});

  async function ensureSubclassOptionMap(
    submodule: keyof typeof enumSubmodule,
  ): Promise<Record<string, Option[]>> {
    const now = Date.now();
    const existing = subclassOptionMapBySubmodule[submodule];
    const last = subclassMapFetchedAt[submodule];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const rawMap = await getSubclassMap(submodule);
    const optionMap: Record<string, Option[]> = {};
    Object.entries(rawMap).forEach(([cls, list]) => {
      optionMap[cls] = (list ?? []).map((s) => ({ label: s, value: s }));
    });

    subclassOptionMapBySubmodule[submodule] = optionMap;
    subclassMapFetchedAt[submodule] = now;

    return optionMap;
  }

  async function fetchClassOptions(
    submodule: AllSubmoduleTypes,
  ): Promise<Option[]> {
    const optionMap = await ensureSubclassOptionMap(submodule);
    const classes = Object.keys(optionMap).sort();
    return classes.map((c) => ({ label: c, value: c }));
  }

  async function fetchSubclassOptions(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
  ): Promise<Option[]> {
    const optionMap = await ensureSubclassOptionMap(submodule);
    return optionMap[equipmentClass] ?? [];
  }

  async function fetchPowerFactor(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
    subClass?: string | null,
  ): Promise<ValueFactorResponse | null> {
    return await getFactorValues(submodule, equipmentClass, subClass);
  }

  return {
    subclassOptionMapBySubmodule,
    subclassMapFetchedAt,
    fetchClassOptions,
    fetchSubclassOptions,
    fetchPowerFactor,
  };
});
