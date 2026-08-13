import type { SimulatorPlanYear } from 'src/stores/simulatorPlans';

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
