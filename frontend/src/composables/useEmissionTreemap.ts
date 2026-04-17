import {
  CHART_CATEGORY_COLOR_SCHEMES,
  CHART_SUBCATEGORY_COLOR_SCHEMES,
} from 'src/constant/charts';
import type {
  EmissionBreakdownCategoryRow,
  EmissionBreakdownValue,
} from 'src/stores/modules';

export interface EmissionTreemapChild {
  name: string;
  value: number;
  percentage: number;
  color: string;
  /** YY-level parent key, present when the child is a ZZ-level item */
  parentKey?: string;
}

export interface EmissionTreemapCategory {
  name: string;
  value: number;
  percentage: number;
  color: string;
  children: EmissionTreemapChild[];
}

// Mirrors backend CATEGORY_CHART_KEYS in emission_breakdown.py
export const CATEGORY_CHART_KEYS: Record<string, string[]> = {
  process_emissions: ['ch4', 'co2', 'n2o', 'refrigerants'],
  buildings_energy_combustion: ['combustion', 'heating_thermal'],
  buildings_room: ['lighting', 'cooling', 'ventilation', 'heating_elec'],
  equipment: ['scientific', 'it', 'other'],
  external_cloud_and_ai: ['clouds', 'ai'],
  purchases: [
    'scientific_equipment',
    'it_equipment',
    'consumable_accessories',
    'biological_chemical_gaseous',
    'services',
    'vehicles',
    'other',
    'additional',
  ],
  research_facilities: ['facilities', 'animal'],
  professional_travel: ['plane', 'train'],
};

/**
 * Categories that should be rendered at YY level (subcategory) rather than
 * drilling to ZZ (item) level. Buildings uses ZZ for room types
 * (office, labs…) which is too granular for the chart.
 */
const YY_LEVEL_CATEGORIES = new Set([
  'buildings_room',
  'buildings_energy_combustion',
  // Cloud items (stockage, virtualisation, calcul) are ZZ keys stored directly
  // on the flat row; AI providers aggregate under the `ai` parent sum.
  // Both are read via flat key lookup rather than the emissions list.
  'external_cloud_and_ai',
]);

/**
 * Builds a treemap hierarchy from module_breakdown rows returned by the API.
 *
 * For most categories, uses the `emissions` list on each row to render the
 * deepest available level (ZZ items such as train class or cabin class),
 * grouping by `parent_key` for color assignment. Categories in
 * `YY_LEVEL_CATEGORIES` are capped at YY (subcategory) level using the
 * pre-aggregated flat parent sums on the row.
 *
 * @param rows - per-category rows from `emission_breakdown.module_breakdown`
 * @param categoryChartKeys - maps each category name to its list of YY parent
 *   keys used for filtering and color lookup
 */
export function buildModuleTreemapData(
  rows: EmissionBreakdownCategoryRow[],
  categoryChartKeys: Record<string, string[]>,
): EmissionTreemapCategory[] {
  const colorByCategory = CHART_CATEGORY_COLOR_SCHEMES.value as Record<
    string,
    string
  >;
  const subcolorByCategory = CHART_SUBCATEGORY_COLOR_SCHEMES.value as Record<
    string,
    Record<string, string>
  >;

  const result: EmissionTreemapCategory[] = [];

  for (const cat of Object.keys(categoryChartKeys)) {
    const row = rows.find((r) => r.category_key === cat || r.category === cat);
    if (!row) continue;

    const subKeys = categoryChartKeys[cat] ?? [];
    const catColor = colorByCategory[cat] ?? '#999999';
    const subColors = subcolorByCategory[cat] ?? {};
    const rawEmissions = (row.emissions as EmissionBreakdownValue[]) ?? [];

    let catTotal: number;
    let children: EmissionTreemapChild[];

    if (
      subKeys.length > 0 &&
      rawEmissions.length > 0 &&
      !YY_LEVEL_CATEGORIES.has(cat)
    ) {
      // Use the emissions list to render the deepest available level (ZZ).
      // Iterate subKeys (CATEGORY_CHART_KEYS order) so treemap left→right
      // matches the breakdown chart top→bottom order.
      children = [];
      for (const parentKey of subKeys) {
        for (const emission of rawEmissions) {
          const emParentKey = emission.parent_key
            ? String(emission.parent_key)
            : String(emission.key);
          if (emParentKey !== parentKey) continue;
          const val = Number(emission.value) || 0;
          if (val <= 0) continue;
          children.push({
            name: emission.key,
            value: val,
            percentage: 0, // filled below
            color: subColors[parentKey] ?? catColor,
            ...(emission.parent_key
              ? { parentKey: String(emission.parent_key) }
              : {}),
          });
        }
      }
      catTotal = children.reduce((s, c) => s + c.value, 0);
    } else if (subKeys.length > 0) {
      // YY-level categories (e.g. buildings) or rows without an emissions
      // array: use the pre-aggregated flat parent sums on the row.
      children = subKeys
        .map((k) => ({
          key: k,
          val: Number((row as Record<string, unknown>)[k]) || 0,
        }))
        .filter(({ val }) => val > 0)
        .map(({ key, val }) => ({
          name: key,
          value: val,
          percentage: 0,
          color: subColors[key] ?? catColor,
        }));
      catTotal = children.reduce((s, c) => s + c.value, 0);
    } else {
      // No predefined subkeys — sum all numeric non-metadata values
      catTotal = Object.entries(row)
        .filter(
          ([k]) =>
            k !== 'category' &&
            k !== 'category_key' &&
            k !== 'emissions' &&
            k !== 'parent_keys_order' &&
            !k.endsWith('StdDev'),
        )
        .reduce((s, [, v]) => s + (Number(v) || 0), 0);
      children = [];
    }

    if (catTotal <= 0) continue;

    children.forEach((c) => {
      c.percentage = (c.value / catTotal) * 100;
    });

    result.push({
      name: cat,
      value: catTotal,
      percentage: 0, // filled after grand total
      color: catColor,
      children,
    });
  }

  const grandTotal = result.reduce((s, c) => s + c.value, 0);
  result.forEach((cat) => {
    cat.percentage = grandTotal > 0 ? (cat.value / grandTotal) * 100 : 0;
  });

  return result;
}

/**
 * Builds a treemap for the results summary page using all module categories.
 *
 * @param moduleBreakdown - `emission_breakdown.module_breakdown` from the API
 */
export function buildResultsTreemapData(
  moduleBreakdown: EmissionBreakdownCategoryRow[],
): EmissionTreemapCategory[] {
  return buildModuleTreemapData(moduleBreakdown, CATEGORY_CHART_KEYS);
}
