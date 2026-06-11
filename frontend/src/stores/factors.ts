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

  // Cached per (submodule, year) — factors are year-scoped, so the same
  // submodule yields different class/subclass maps across years.
  const subclassOptionMapByKey = reactive<
    Record<string, Record<string, Option[]>>
  >({});
  const subclassMapFetchedAt = reactive<Record<string, number>>({});

  function cacheKey(
    submodule: keyof typeof enumSubmodule,
    year: number | string,
  ): string {
    return `${submodule}:${year}`;
  }

  async function ensureSubclassOptionMap(
    submodule: keyof typeof enumSubmodule,
    year: number | string,
  ): Promise<Record<string, Option[]>> {
    const now = Date.now();
    const key = cacheKey(submodule, year);
    const existing = subclassOptionMapByKey[key];
    const last = subclassMapFetchedAt[key];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const rawMap = await getSubclassMap(submodule, year);
    const optionMap: Record<string, Option[]> = {};
    Object.entries(rawMap).forEach(([cls, list]) => {
      optionMap[cls] = (list ?? []).map((s) => ({ label: s, value: s }));
    });

    subclassOptionMapByKey[key] = optionMap;
    subclassMapFetchedAt[key] = now;

    return optionMap;
  }

  async function fetchClassOptions(
    submodule: AllSubmoduleTypes,
    year: number | string,
  ): Promise<Option[]> {
    const optionMap = await ensureSubclassOptionMap(submodule, year);
    const classes = Object.keys(optionMap);
    return classes.map((c) => ({ label: c, value: c }));
  }

  async function fetchSubclassOptions(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
    year: number | string,
  ): Promise<Option[]> {
    const optionMap = await ensureSubclassOptionMap(submodule, year);
    return optionMap[equipmentClass] ?? [];
  }

  async function fetchPowerFactor(
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
    subClass?: string | null,
    year?: string | number | null,
  ): Promise<ValueFactorResponse | null> {
    return await getFactorValues(submodule, equipmentClass, subClass, year);
  }

  return {
    subclassOptionMapByKey,
    subclassMapFetchedAt,
    fetchClassOptions,
    fetchSubclassOptions,
    fetchPowerFactor,
  };
});
