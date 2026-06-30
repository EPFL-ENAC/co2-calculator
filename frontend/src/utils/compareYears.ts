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
  const yearSet = new Set(selectedYears);
  let total = 0;
  for (const entry of years) {
    if (!yearSet.has(entry.year)) continue;
    for (const key of selectedCategories) {
      total += entry.modules[key] ?? 0;
    }
  }
  return total;
}

export interface CompareYearsObjective {
  targetYear: number;
  valueTonnes: number;
}

/**
 * The "objective" bar appended to the by-module chart: the latest reduction
 * goal (last entry in `goals`) applied to the latest selected year's
 * selected-category total — i.e. `baseline × (1 − reduction_percentage)`.
 * Returns `null` when there is no goal, no selected year, or a zero baseline,
 * so the caller simply omits the bar.
 */
export function computeCompareYearsObjective(
  years: CompareYearsEntry[],
  selectedYears: number[],
  selectedCategories: string[],
  goals: ReductionObjectiveGoal[],
): CompareYearsObjective | null {
  const goal = goals.at(-1);
  if (!goal || selectedYears.length === 0) return null;
  const latestYear = Math.max(...selectedYears);
  const baseline = computeCompareYearsTotal(
    years,
    [latestYear],
    selectedCategories,
  );
  if (baseline <= 0) return null;
  return {
    targetYear: goal.target_year,
    valueTonnes: baseline * (1 - goal.reduction_percentage),
  };
}
