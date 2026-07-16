/**
 * Adapters from the persisted `carbon_report.stats` shape (written by the
 * backend recompute — see backend `app/utils/report_stats.py`) to the row
 * shapes the results charts render. All kg values arrive from the backend;
 * this file only reshapes and converts kg → tonnes for display.
 */

import { EMISSION_TYPE_NAMES } from 'src/types/emission-taxonomy.gen';
import type {
  EmbodiedEnergyCategoryEntry,
  EmissionBreakdownCategoryRow,
  EmissionBreakdownResponse,
  EmissionBreakdownValue,
  ItBreakdownCategory,
  ItBreakdownResponse,
} from 'src/stores/modules';

export interface BucketStats {
  scope: number;
  additional: boolean;
  total_kg: number;
  by_emission_type: Record<string, number>;
  by_additional_value?: Record<string, number>;
  by_building?: {
    building_name: string;
    kg_co2eq: number;
    tonnes_co2eq: number;
  }[];
  by_category?: EmbodiedEnergyCategoryEntry[];
}

/** Physical-quantity donut data, derived by the backend per bucket. */
export interface QuantitySection {
  unit: string;
  by_emission_type: Record<string, number>;
}

export interface ItStats {
  total_kg: number;
  percentage_of_total: number;
  per_fte: number;
  percentage_of_source_modules: number;
  categories: Record<string, number>;
  cloud_ai_detail: Record<string, number>;
  validated_sources: string[];
  top_class_detail: Record<
    string,
    { name: string; children?: { name: string; value: number }[] }[]
  >;
}

export interface ReportStats {
  buckets: Record<string, BucketStats>;
  per_fte: Record<string, number>;
  quantities?: Record<string, QuantitySection>;
  validated_buckets: string[];
  total: number;
  validated_total?: number;
  total_fte: number;
  total_tonnes_validated_co2eq?: number;
  it: ItStats;
  [key: string]: unknown;
}

/** Bucket keys per module_type_id, for the exclude_modules display filter. */
const BUCKETS_BY_MODULE_TYPE_ID: Record<number, string[]> = {
  1: ['commuting', 'food', 'waste'],
  2: ['professional_travel'],
  3: ['buildings_energy_combustion', 'buildings_room', 'embodied_energy'],
  4: ['equipment'],
  5: ['purchases'],
  6: ['research_facilities'],
  7: ['external_cloud_and_ai'],
  8: ['process_emissions'],
};

const IT_CATEGORY_TO_BUCKET_KEY: Record<string, string> = {
  equipment_it: 'equipment',
  purchases_it: 'purchases',
  external_cloud_and_ai: 'external_cloud_and_ai',
  research_facilities_it: 'research_facilities',
};

function excludedBucketKeys(excludeModules: number[]): Set<string> {
  const keys = new Set<string>();
  for (const moduleTypeId of excludeModules) {
    for (const key of BUCKETS_BY_MODULE_TYPE_ID[moduleTypeId] ?? []) {
      keys.add(key);
    }
  }
  return keys;
}

/**
 * Leaf entries of a bucket map: ids whose name prefixes no other id's name.
 *
 * Ids are taken from both maps: a zero-emission type (walking) is absent from
 * `by_emission_type` but still carries kilometres in the backend-derived
 * `quantities` section.
 */
function leafEntries(
  byEmissionType: Record<string, number>,
  byQuantity?: Record<string, number>,
): { id: number; name: string; kg: number }[] {
  const ids = new Set([
    ...Object.keys(byEmissionType),
    ...Object.keys(byQuantity ?? {}),
  ]);
  const entries = [...ids].map((idStr) => ({
    id: Number(idStr),
    name: EMISSION_TYPE_NAMES[Number(idStr)] ?? idStr,
    kg: byEmissionType[idStr] ?? 0,
  }));
  const names = new Set(entries.map((entry) => entry.name));
  return entries.filter((entry) => {
    for (const name of names) {
      if (name !== entry.name && name.startsWith(`${entry.name}__`)) {
        return false;
      }
    }
    return true;
  });
}

function buildCategoryRow(
  bucketKey: string,
  bucket: BucketStats,
  quantities?: QuantitySection,
): EmissionBreakdownCategoryRow {
  const row: EmissionBreakdownCategoryRow = {
    category: bucketKey,
    category_key: bucketKey,
    scope: bucket.scope,
    additional: bucket.additional,
    emissions: [],
    parent_keys_order: [],
  };
  const emissions: EmissionBreakdownValue[] = [];
  const parentSums: Record<string, number> = {};
  const seenBarKeys = new Set<string>();

  const leaves = leafEntries(
    bucket.by_emission_type,
    quantities?.by_emission_type,
  ).sort((a, b) => a.id - b.id);
  for (const leaf of leaves) {
    const segments = leaf.name.split('__');
    const key = segments[segments.length - 1];
    const quantity = quantities?.by_emission_type[String(leaf.id)];
    const unit = quantities?.unit;
    const hasQuantity = quantity != null && quantity > 0 && unit != null;
    // A zero-emission mode (walking) still belongs in the physical-quantity
    // charts, which read `emissions` and filter on quantity themselves.
    if (leaf.kg <= 0 && !hasQuantity) continue;

    const value = leaf.kg / 1000.0;
    const emission: EmissionBreakdownValue = {
      emission_type: leaf.name,
      key,
      value,
    };
    if (segments.length >= 3) {
      emission.parent_key = segments[segments.length - 2];
    }
    if (quantity != null && unit) {
      emission.quantity = quantity;
      emission.quantity_unit = unit;
    }
    emissions.push(emission);

    // Numeric row keys feed the CO2 bar chart and the treemap: a zero-kg leaf
    // contributes nothing there and would only add an empty bar.
    if (leaf.kg <= 0) continue;
    row[key] = ((row[key] as number) ?? 0) + value;
    if (emission.parent_key) {
      parentSums[emission.parent_key] =
        (parentSums[emission.parent_key] ?? 0) + value;
    }
    const barKey = emission.parent_key ?? key;
    if (!seenBarKeys.has(barKey)) {
      seenBarKeys.add(barKey);
      row.parent_keys_order.push(barKey);
    }
  }
  row.emissions = emissions;
  for (const [parentKey, value] of Object.entries(parentSums)) {
    row[parentKey] = ((row[parentKey] as number) ?? 0) + value;
  }
  return row;
}

export function toEmissionBreakdown(
  stats: ReportStats,
  excludeModules: number[] = [],
  moduleStates?: { module_type_id: number; status: number }[],
): EmissionBreakdownResponse {
  const excluded = excludedBucketKeys(excludeModules);
  const moduleRows: EmissionBreakdownCategoryRow[] = [];
  const additionalRows: EmissionBreakdownCategoryRow[] = [];
  let totalKg = 0;

  for (const [bucketKey, bucket] of Object.entries(stats.buckets ?? {})) {
    if (excluded.has(bucketKey)) continue;
    const row = buildCategoryRow(
      bucketKey,
      bucket,
      stats.quantities?.[bucketKey],
    );
    (bucket.additional ? additionalRows : moduleRows).push(row);
    totalKg += bucket.total_kg ?? 0;
  }

  const validated = stats.validated_buckets ?? [];
  const perPerson: Record<string, number> = {};
  for (const [bucketKey, value] of Object.entries(stats.per_fte ?? {})) {
    if (!excluded.has(bucketKey)) perPerson[bucketKey] = value;
  }

  const embodied = stats.buckets?.embodied_energy;
  return {
    module_breakdown: moduleRows,
    additional_breakdown: additionalRows,
    per_person_breakdown: perPerson,
    validated_categories: validated.filter((key) => !excluded.has(key)),
    headcount_validated: validated.includes('food'),
    buildings_validated: validated.includes('buildings_room'),
    total_tonnes_co2eq: totalKg / 1000.0,
    total_tonnes_validated_co2eq: stats.total_tonnes_validated_co2eq,
    total_fte: stats.total_fte ?? 0,
    it_summary: {
      total_tonnes_co2eq: (stats.it?.total_kg ?? 0) / 1000.0,
      percentage_of_total: stats.it?.percentage_of_total ?? 0,
    },
    embodied_energy_by_category: embodied?.by_category ?? [],
    embodied_energy_by_building: embodied?.by_building ?? [],
    module_states: moduleStates,
  };
}

const IT_CATEGORIES_ORDER = [
  'equipment_it',
  'purchases_it',
  'external_cloud_and_ai',
  'research_facilities_it',
];

export function toItBreakdown(
  stats: ReportStats,
  excludeModules: number[] = [],
): ItBreakdownResponse {
  const excluded = excludedBucketKeys(excludeModules);
  const it = stats.it;
  const activeCategories = IT_CATEGORIES_ORDER.filter(
    (category) => !excluded.has(IT_CATEGORY_TO_BUCKET_KEY[category]),
  );
  const totalItKg = activeCategories.reduce(
    (sum, category) => sum + (it?.categories?.[category] ?? 0),
    0,
  );

  const categories: ItBreakdownCategory[] = activeCategories.map((category) => {
    const kg = it?.categories?.[category] ?? 0;
    const entry: ItBreakdownCategory = {
      category_key: category,
      tonnes_co2eq: kg / 1000.0,
      percentage: totalItKg > 0 ? (kg / totalItKg) * 100.0 : 0,
    };
    if (category === 'external_cloud_and_ai') {
      const detail = Object.entries(it?.cloud_ai_detail ?? {});
      if (detail.length > 0) {
        entry.emissions = detail
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, kgValue]) => ({ key, value: kgValue / 1000.0 }));
        entry.top_items = detail
          .sort(([, a], [, b]) => b - a)
          .map(([name, kgValue]) => ({ name, value: kgValue / 1000.0 }));
      }
    } else {
      const topClasses = it?.top_class_detail?.[category];
      if (topClasses) {
        const items = topClasses.flatMap((subcategory) =>
          (subcategory.children ?? []).map((child) => ({
            name: child.name,
            value: child.value / 1000.0,
          })),
        );
        items.sort((a, b) =>
          a.name === 'rest' ? 1 : b.name === 'rest' ? -1 : b.value - a.value,
        );
        entry.top_items = items;
      }
    }
    return entry;
  });

  const validatedSources = (it?.validated_sources ?? []).filter((category) =>
    activeCategories.includes(category),
  );
  const allValidated =
    activeCategories.length > 0 &&
    validatedSources.length === activeCategories.length;

  const scope2Kg = excluded.has('equipment')
    ? 0
    : (it?.categories?.equipment_it ?? 0);
  return {
    total_it_tonnes_co2eq: totalItKg / 1000.0,
    total_it_per_fte: it?.per_fte ?? 0,
    percentage_of_total: it?.percentage_of_total ?? 0,
    percentage_of_source_modules: it?.percentage_of_source_modules ?? 0,
    categories,
    scope_breakdown: {
      scope_2: scope2Kg / 1000.0,
      scope_3: (totalItKg - scope2Kg) / 1000.0,
    },
    validated: allValidated,
    partially_validated: validatedSources.length > 0 && !allValidated,
    validated_sources: validatedSources,
  };
}
