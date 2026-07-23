import type { EmissionBreakdownResponse } from 'src/stores/modules';

/**
 * Total tonnes summed off the same rows the module chart draws, so a headline
 * figure and the bars beneath it always agree.
 *
 * Deliberately not `stats.total` from the backend: that counts every bucket,
 * including the additional categories (commuting, food, waste, embodied
 * energy) which `module_breakdown` — and so the chart — leaves out. Reading it
 * here would put a headline on the page that the bars below it contradict,
 * which is the buildings-banner discrepancy all over again.
 *
 * The backend has no module-only total to read instead; adding one (as the
 * banner fix did for a single module) would retire this helper.
 */
export function sumBreakdownTonnes(
  breakdown: EmissionBreakdownResponse | null | undefined,
): number {
  if (!breakdown) return 0;
  const moduleTotal = (breakdown.module_breakdown ?? []).reduce((sum, row) => {
    const rowTotal = (row.emissions ?? []).reduce(
      (rowSum, emission) =>
        rowSum + (typeof emission.value === 'number' ? emission.value : 0),
      0,
    );
    return sum + rowTotal;
  }, 0);
  return moduleTotal || breakdown.total_tonnes_co2eq || 0;
}
