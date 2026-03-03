import { computed } from 'vue';
import type { ComputedRef } from 'vue';
import type { EmissionBreakdownResponse } from 'src/stores/modules';
import {
  CHART_CATEGORY_COLOR_SCHEMES,
  MODULE_TO_CATEGORIES,
} from 'src/constant/charts';

export interface EmissionTreemapChild {
  name: string;
  value: number;
  percentage?: number;
}

export interface EmissionTreemapCategory {
  name: string;
  value: number;
  color: string;
  children: EmissionTreemapChild[];
}

function buildTreemapFromRows(
  breakdown: EmissionBreakdownResponse,
  categories: string[],
): EmissionTreemapCategory[] {
  const colorSchemes = CHART_CATEGORY_COLOR_SCHEMES.value;
  const result: EmissionTreemapCategory[] = [];

  for (const row of breakdown.module_breakdown) {
    const category = row.category as string;
    if (!categories.includes(category)) continue;

    const children: EmissionTreemapChild[] = [];
    for (const [key, val] of Object.entries(row)) {
      if (key === 'category' || key.endsWith('StdDev')) continue;
      const value = Number(val);
      if (value > 0) {
        children.push({ name: key, value });
      }
    }

    if (children.length === 0) continue;

    const total = children.reduce((sum, c) => sum + c.value, 0);
    if (total <= 0) continue;

    const childrenWithPct = children.map((c) => ({
      ...c,
      percentage: (c.value / total) * 100,
    }));

    result.push({
      name: category,
      value: total,
      color: colorSchemes[category] ?? '#999999',
      children: childrenWithPct,
    });
  }

  return result;
}

/**
 * Build treemap data for the full results overview (all module categories).
 */
export function buildResultsTreemapData(
  breakdown: EmissionBreakdownResponse | null,
): EmissionTreemapCategory[] {
  if (!breakdown) return [];
  const allCategories = Object.keys(CHART_CATEGORY_COLOR_SCHEMES.value);
  return buildTreemapFromRows(breakdown, allCategories);
}

/**
 * Build treemap data filtered to one module's categories.
 * @param breakdown - emission breakdown from the store
 * @param moduleKey - Module enum value, e.g. 'equipment-electric-consumption'
 */
export function buildModuleTreemapData(
  breakdown: EmissionBreakdownResponse | null,
  moduleKey: string,
): EmissionTreemapCategory[] {
  if (!breakdown) return [];
  const categories = MODULE_TO_CATEGORIES.value[moduleKey] ?? [];
  if (categories.length === 0) return [];
  return buildTreemapFromRows(breakdown, categories);
}

/**
 * Composable versions that return reactive computed refs.
 */
export function useResultsTreemapData(
  breakdown: ComputedRef<EmissionBreakdownResponse | null | undefined>,
): ComputedRef<EmissionTreemapCategory[]> {
  return computed(() => buildResultsTreemapData(breakdown.value ?? null));
}

export function useModuleTreemapData(
  breakdown: ComputedRef<EmissionBreakdownResponse | null | undefined>,
  moduleKey: ComputedRef<string>,
): ComputedRef<EmissionTreemapCategory[]> {
  return computed(() =>
    buildModuleTreemapData(breakdown.value ?? null, moduleKey.value),
  );
}
