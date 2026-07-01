import type { CompareYearsEntry } from 'src/stores/modules';
import type { ReductionObjectiveGoal } from 'src/stores/yearConfig';

/**
 * Pure helpers for the "Compare Years" dialog. Kept out of the component so the
 * selection/total logic is unit-testable without mounting Vue.
 */

/** Years that carry any emissions — the default year selection. */
export function defaultSelectedYears(years: CompareYearsEntry[]): number[] {
  return years.filter((y) => y.total_tonnes_co2eq > 0).map((y) => y.year);
}

/**
 * Category keys (in the supplied order) that appear with a positive value in at
 * least one year — the default category selection / available options.
 */
export function presentCategories(
  years: CompareYearsEntry[],
  order: readonly string[],
): string[] {
  return order.filter((key) => years.some((y) => (y.modules[key] ?? 0) > 0));
}

/** The per-year dimension a selection is summed over. */
export type CompareYearsDimension = 'modules' | 'scopes';

/**
 * Sum tonnes CO2eq over selected years × selected keys for a given dimension
 * (`modules` = category keys, `scopes` = "1" | "2" | "3").
 */
function sumSelected(
  years: CompareYearsEntry[],
  selectedYears: number[],
  selectedKeys: string[],
  dimension: CompareYearsDimension,
): number {
  const yearSet = new Set(selectedYears);
  let total = 0;
  for (const entry of years) {
    if (!yearSet.has(entry.year)) continue;
    const bucket = dimension === 'scopes' ? entry.scopes : entry.modules;
    for (const key of selectedKeys) {
      total += bucket[key] ?? 0;
    }
  }
  return total;
}

/**
 * Total tonnes CO2eq for the active selection: selected years × selected
 * categories. Deselecting a category lowers the total, matching the stacked bar
 * chart it drives.
 */
export function computeCompareYearsTotal(
  years: CompareYearsEntry[],
  selectedYears: number[],
  selectedCategories: string[],
): number {
  return sumSelected(years, selectedYears, selectedCategories, 'modules');
}

export interface CompareYearsObjective {
  targetYear: number;
  /** Closest available unit year used as the reduction baseline. */
  referenceYear: number;
  valueTonnes: number;
}

/**
 * The unit's baseline year for a goal: among breakdown years whose selected-key
 * total (in the given dimension) is positive, the one closest to the goal's
 * institution `referenceYear`. Ties resolve to the earlier year. Returns `null`
 * when no year carries a positive baseline for the selection.
 */
export function closestAvailableYear(
  years: CompareYearsEntry[],
  referenceYear: number,
  selectedKeys: string[],
  dimension: CompareYearsDimension = 'modules',
): number | null {
  let best: number | null = null;
  let bestDist = Infinity;
  for (const entry of years) {
    if (sumSelected(years, [entry.year], selectedKeys, dimension) <= 0)
      continue;
    const dist = Math.abs(entry.year - referenceYear);
    // Strictly-less keeps the earliest year on ties (years may arrive unsorted).
    if (
      dist < bestDist ||
      (dist === bestDist && best != null && entry.year < best)
    ) {
      best = entry.year;
      bestDist = dist;
    }
  }
  return best;
}

/**
 * One objective bar per reduction goal, sorted ascending by target year. For
 * each goal the target is the unit's baseline at the year closest to that
 * goal's institution `reference_year`, reduced by its percentage —
 * `baseline × (1 − reduction_percentage)`. The baseline is selection-aware
 * (restricted to `selectedKeys` in the given dimension), so the bars stay
 * comparable to the visible stacked bars. Goals with no positive baseline year
 * are skipped.
 */
export function computeCompareYearsObjectives(
  years: CompareYearsEntry[],
  selectedKeys: string[],
  goals: ReductionObjectiveGoal[],
  dimension: CompareYearsDimension = 'modules',
): CompareYearsObjective[] {
  const objectives: CompareYearsObjective[] = [];
  for (const goal of goals) {
    const refYear = closestAvailableYear(
      years,
      goal.reference_year,
      selectedKeys,
      dimension,
    );
    if (refYear == null) continue;
    const baseline = sumSelected(years, [refYear], selectedKeys, dimension);
    if (baseline <= 0) continue;
    objectives.push({
      targetYear: goal.target_year,
      referenceYear: refYear,
      valueTonnes: baseline * (1 - goal.reduction_percentage),
    });
  }
  return objectives.sort((a, b) => a.targetYear - b.targetYear);
}
