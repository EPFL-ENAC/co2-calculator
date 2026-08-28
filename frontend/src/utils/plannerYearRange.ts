import type { SimulatorPlanYear } from '@/stores/simulatorPlans';

/**
 * Reference-year default: last calendar year when it's open, else the
 * latest open year. `null` when no year is open at all — callers must not
 * PATCH a null `reference_year` (issue #2459).
 */
export function resolveDefaultReferenceYear(
  open: Set<number>,
  currentYear: number,
): number | null {
  const lastYear = currentYear - 1;
  if (open.has(lastYear)) return lastYear;
  if (open.size === 0) return null;
  return Math.max(...open);
}

export function formatYearRange(
  first?: number | null,
  last?: number | null,
): string {
  if (first == null && last == null) return '';
  if (first == null || last == null || first === last) {
    return String(first ?? last);
  }
  return `${first} > ${last}`;
}

/** Range spanned by the plan years that actually hold emissions. */
export function filledYearRange(years: SimulatorPlanYear[]): string {
  const filled = years
    .filter(
      (y) =>
        !y.is_grant &&
        Number((y.stats as { total?: unknown } | null)?.total ?? 0) > 0,
    )
    .map((y) => y.year);
  if (!filled.length) return '';
  return formatYearRange(Math.min(...filled), Math.max(...filled));
}

export function withYearRange(label: string, range: string): string {
  return range ? `${label} (${range})` : label;
}
