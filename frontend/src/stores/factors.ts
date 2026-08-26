import { defineStore } from 'pinia';
import { reactive } from 'vue';
import {
  getSubclassMap,
  getFactorValues,
  listFactors,
  type ValueFactorResponse,
} from '@/api/factors';
import { type AllSubmoduleTypes, enumSubmodule } from '@/constant/modules';
import { toClassOptions, type FactorRow } from '@/utils/factorOptions';

type Option = { label: string; value: string };

export const useFactorsStore = defineStore('factors', () => {
  const ONE_MINUTE_MS = 60_000;

  // Cached per (submodule, year) — factors are year-scoped, so the same
  // submodule yields different class/subclass maps across years.
  const subclassOptionMapByKey = reactive<
    Record<string, Record<string, Option[]>>
  >({});
  const subclassMapFetchedAt = reactive<Record<string, number>>({});

  // Same key and TTL for the factor catalog. Plain objects, not `reactive`:
  // unlike the subclass map (which ModuleTable renders from) nothing watches
  // this — it is only ever read inside the fetch below.
  const factorListByKey: Record<string, FactorRow[]> = {};
  const factorListFetchedAt: Record<string, number> = {};

  // In-flight lookups for the same key share one request: several forms for
  // the same submodule mounting at once would otherwise each fire the same
  // GET before the first write lands (#2360). Rejections are never stored —
  // a failed lookup retries on the next call.
  const subclassMapInFlight = new Map<
    string,
    Promise<Record<string, Option[]>>
  >();
  const factorListInFlight = new Map<string, Promise<FactorRow[]>>();

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

    const inFlight = subclassMapInFlight.get(key);
    if (inFlight) return inFlight;

    const request = (async () => {
      const rawMap = await getSubclassMap(submodule, year);
      const optionMap: Record<string, Option[]> = {};
      Object.entries(rawMap).forEach(([cls, list]) => {
        optionMap[cls] = (list ?? []).map((s) => ({ label: s, value: s }));
      });

      subclassOptionMapByKey[key] = optionMap;
      subclassMapFetchedAt[key] = now;

      return optionMap;
    })();
    subclassMapInFlight.set(key, request);
    try {
      return await request;
    } finally {
      subclassMapInFlight.delete(key);
    }
  }

  /**
   * Class options for a `kind` select. By default the class value is also its
   * label (equipment classes are already readable). ``labels`` switches the
   * source to the factor catalog, for classifications stored as opaque codes
   * that need a separate name field to display (#2007).
   */
  async function fetchClassOptions(
    submodule: AllSubmoduleTypes,
    year: number | string,
    labels?: { valueField: string; labelField: string },
  ): Promise<Option[]> {
    if (labels) return fetchLabelledClassOptions(submodule, year, labels);
    const optionMap = await ensureSubclassOptionMap(submodule, year);
    const classes = Object.keys(optionMap);
    return classes.map((c) => ({ label: c, value: c }));
  }

  async function ensureFactorList(
    submodule: keyof typeof enumSubmodule,
    year: number | string,
  ): Promise<FactorRow[]> {
    const now = Date.now();
    const key = cacheKey(submodule, year);
    const existing = factorListByKey[key];
    const last = factorListFetchedAt[key];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const inFlight = factorListInFlight.get(key);
    if (inFlight) return inFlight;

    const request = (async () => {
      const rows = await listFactors(submodule, year);
      factorListByKey[key] = rows;
      factorListFetchedAt[key] = now;

      return rows;
    })();
    factorListInFlight.set(key, request);
    try {
      return await request;
    } finally {
      factorListInFlight.delete(key);
    }
  }

  async function fetchLabelledClassOptions(
    submodule: AllSubmoduleTypes,
    year: number | string,
    { valueField, labelField }: { valueField: string; labelField: string },
  ): Promise<Option[]> {
    // Cache the rows, not the options: the catalog is field-agnostic, so a
    // second select over the same submodule reuses the one fetch.
    const rows = await ensureFactorList(submodule, year);
    return toClassOptions(rows, valueField, labelField);
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
