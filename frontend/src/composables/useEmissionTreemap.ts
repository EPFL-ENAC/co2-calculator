import {
  CHART_CATEGORY_COLOR_SCHEMES,
  CHART_SUBCATEGORY_COLOR_SCHEMES,
} from 'src/constant/charts';

export interface EmissionTreemapChild {
  name: string;
  value: number;
  percentage: number;
  color: string;
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
  'Process Emissions': ['process_emissions'],
  'Buildings energy combustion': ['heating_thermal', 'combustion'],
  'Buildings room': ['lighting', 'cooling', 'ventilation', 'heating_elec'],
  Equipment: ['scientific', 'it', 'other'],
  'External cloud & AI': [
    'stockage',
    'virtualisation',
    'calcul',
    'ai_provider',
  ],
  Purchases: [
    'scientific_equipment',
    'it_equipment',
    'consumable_accessories',
    'biological_chemical_gaseous',
    'services',
    'vehicles',
    'other',
    'additional',
  ],
  'Research facilities': [],
  'Professional travel': ['plane', 'train'],
};

/**
 * Builds a treemap hierarchy from flat module_breakdown rows returned by the API.
 *
 * @param rows - flat per-category rows from `emission_breakdown.module_breakdown`
 * @param categoryChartKeys - maps each category name to its list of subcategory keys;
 *   pass a subset of CATEGORY_CHART_KEYS to filter to specific module categories
 */
export function buildModuleTreemapData(
  rows: Array<{ category: string; [key: string]: number | string }>,
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
    const row = rows.find((r) => r.category === cat);
    if (!row) continue;

    const subKeys = categoryChartKeys[cat] ?? [];
    const catColor = colorByCategory[cat] ?? '#999999';
    const subColors = subcolorByCategory[cat] ?? {};

    let catTotal: number;
    let children: EmissionTreemapChild[];

    if (subKeys.length > 0) {
      children = subKeys
        .map((k) => ({ key: k, val: Number(row[k]) || 0 }))
        .filter(({ val }) => val > 0)
        .map(({ key, val }) => ({
          name: key,
          value: val,
          percentage: 0, // filled below
          color: subColors[key] ?? catColor,
        }));
      catTotal = children.reduce((s, c) => s + c.value, 0);
    } else {
      // No predefined subkeys — sum all numeric non-metadata values
      catTotal = Object.entries(row)
        .filter(([k]) => k !== 'category' && !k.endsWith('StdDev'))
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
  moduleBreakdown: Array<{ category: string; [key: string]: number | string }>,
): EmissionTreemapCategory[] {
  return buildModuleTreemapData(moduleBreakdown, CATEGORY_CHART_KEYS);
}
