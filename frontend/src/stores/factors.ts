import { defineStore } from 'pinia';
import { computed, markRaw, reactive } from 'vue';
import { getFactorValues, type ValueFactorResponse } from '@/api/factors';
import { getDataEntryTaxonomy } from '@/api/taxonomies';
import type { AllSubmoduleTypes, TaxonomyNode } from '@/constant/modules';

type Option = { label: string; value: string };

function byLabel(a: Option, b: Option): number {
  return a.label.localeCompare(b.label);
}

/**
 * Distinct child options of a kind node, in the order the selects render.
 *
 * Not sorted: the classification value IS the label here (a gas type, a
 * cloud provider, …), and the backend's declared order can carry meaning
 * (e.g. CO2/CH4/SF6 in GHG-protocol order) that an alphabetical resort
 * would silently discard. `fetchClassOptions`'s `labelled` case — an
 * opaque id mapped to a human name — sorts explicitly, because that's the
 * one shape a long, browsable list needs it (#2007).
 */
function subclassOptionsOf(kind: TaxonomyNode): Option[] {
  const byName = new Map<string, Option>();
  for (const child of kind.children ?? []) {
    if (!byName.has(child.name))
      byName.set(child.name, { label: child.name, value: child.name });
  }
  return [...byName.values()];
}

export const useFactorsStore = defineStore('factors', () => {
  const ONE_MINUTE_MS = 60_000;

  // Cached per (submodule, year) — factors are year-scoped, so the same
  // submodule yields a different tree across years. The module is fixed by
  // the submodule, so it never varies independently of this key.
  // `markRaw`: the tree is read-only and can hold ~10k nodes (purchase);
  // deep-proxying it would cost more than every read it serves.
  const taxonomyByKey = reactive<Record<string, TaxonomyNode>>({});
  const taxonomyFetchedAt: Record<string, number> = {};

  // In-flight lookups for the same key share one request: several forms for
  // the same submodule mounting at once would otherwise each fire the same
  // GET before the first write lands (#2360). Rejections are never stored —
  // a failed lookup retries on the next call.
  const taxonomyInFlight = new Map<string, Promise<TaxonomyNode>>();

  /**
   * kind -> subkind options, keyed like `taxonomyByKey`. ModuleTable reads it
   * directly to decide whether a row's subcategory is required, so it stays a
   * reactive projection of the cached trees rather than a second cache.
   */
  const subclassOptionMapByKey = computed(() => {
    const maps: Record<string, Record<string, Option[]>> = {};
    for (const [key, node] of Object.entries(taxonomyByKey)) {
      const map: Record<string, Option[]> = {};
      for (const kind of node.children ?? []) {
        map[kind.name] = subclassOptionsOf(kind);
      }
      maps[key] = map;
    }
    return maps;
  });

  function cacheKey(
    submodule: AllSubmoduleTypes,
    year: number | string,
  ): string {
    return `${submodule}:${year}`;
  }

  async function ensureTaxonomy(
    module: string,
    submodule: AllSubmoduleTypes,
    year: number | string,
  ): Promise<TaxonomyNode> {
    const now = Date.now();
    const key = cacheKey(submodule, year);
    const existing = taxonomyByKey[key];
    const last = taxonomyFetchedAt[key];

    if (existing && last && now - last < ONE_MINUTE_MS) {
      return existing;
    }

    const inFlight = taxonomyInFlight.get(key);
    if (inFlight) return inFlight;

    const request = (async () => {
      const node = markRaw(await getDataEntryTaxonomy(module, submodule, year));
      taxonomyByKey[key] = node;
      taxonomyFetchedAt[key] = now;
      return node;
    })();
    taxonomyInFlight.set(key, request);
    try {
      return await request;
    } finally {
      taxonomyInFlight.delete(key);
    }
  }

  /**
   * Options for a `kind` select. By default the class value is also its label
   * (equipment classes are already readable, and the i18n fallback in
   * `useEquipmentClassOptions` keys off the raw value) — the backend's own
   * order is kept, since for a plain classification list (a gas type, a
   * cloud provider, …) that order can be meaningful and isn't ours to
   * discard. `labelled` switches to the node's server-side label, for
   * classifications stored as opaque codes — a research facility id reads
   * as its acronym (#2007) — and a long id-keyed list is sorted so it stays
   * browsable.
   */
  async function fetchClassOptions(
    module: string,
    submodule: AllSubmoduleTypes,
    year: number | string,
    labelled = false,
  ): Promise<Option[]> {
    const node = await ensureTaxonomy(module, submodule, year);
    const options = (node.children ?? []).map((kind) => ({
      label: labelled ? kind.label : kind.name,
      value: kind.name,
    }));
    return labelled ? options.sort(byLabel) : options;
  }

  async function fetchSubclassOptions(
    module: string,
    submodule: AllSubmoduleTypes,
    equipmentClass: string,
    year: number | string,
  ): Promise<Option[]> {
    // Through the map, not a scan of `children`: one inline-select cell per
    // table row calls this on mount, and purchase trees hold ~10k kind nodes.
    await ensureTaxonomy(module, submodule, year);
    const key = cacheKey(submodule, year);
    return subclassOptionMapByKey.value[key]?.[equipmentClass] ?? [];
  }

  /**
   * The submodule's kind nodes, for callers that build their own rows out of
   * a node's label/meta/children rather than plain options (the planner
   * research-facility grid). Same TTL cache and in-flight dedup as every
   * other lookup — no component calls `api.get` for lookup data (#2391).
   */
  async function fetchClassNodes(
    module: string,
    submodule: AllSubmoduleTypes,
    year: number | string,
  ): Promise<TaxonomyNode[]> {
    const node = await ensureTaxonomy(module, submodule, year);
    return node.children ?? [];
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
    fetchClassOptions,
    fetchClassNodes,
    fetchSubclassOptions,
    fetchPowerFactor,
  };
});
