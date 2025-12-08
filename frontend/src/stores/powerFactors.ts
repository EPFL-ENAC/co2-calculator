import { defineStore } from 'pinia';
import {
  getSubclassMap,
  getPowerFactor,
  SubmoduleKey,
  PowerFactorResponse,
} from 'src/api/powerFactors';

type Option = { label: string; value: string };

export const usePowerFactorsStore = defineStore('power-factors', () => {
  const ONE_MINUTE_MS = 60_000;

  const subclassOptionMapBySubmodule: Partial<
    Record<SubmoduleKey, Record<string, Option[]>>
  > = {};
  const subclassMapFetchedAt: Partial<Record<SubmoduleKey, number>> = {};

  async function ensureSubclassOptionMap(
    submodule: SubmoduleKey,
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

  async function fetchClassOptions(submodule: SubmoduleKey): Promise<Option[]> {
    const optionMap = await ensureSubclassOptionMap(submodule);
    const classes = Object.keys(optionMap).sort();
    return classes.map((c) => ({ label: c, value: c }));
  }

  async function fetchSubclassOptions(
    submodule: SubmoduleKey,
    equipmentClass: string,
  ): Promise<Option[]> {
    const optionMap = await ensureSubclassOptionMap(submodule);
    return optionMap[equipmentClass] ?? [];
  }

  async function fetchPowerFactor(
    submodule: SubmoduleKey,
    equipmentClass: string,
    subClass?: string | null,
  ): Promise<PowerFactorResponse | null> {
    return await getPowerFactor(submodule, equipmentClass, subClass);
  }

  return {
    fetchClassOptions,
    fetchSubclassOptions,
    fetchPowerFactor,
  };
});
