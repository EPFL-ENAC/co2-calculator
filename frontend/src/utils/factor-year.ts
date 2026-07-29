/**
 * Resolve the year whose factors a data entry's dropdowns must offer.
 *
 * The backend resolves factors from ``reference_year`` when the report has one
 * and falls back to ``year`` otherwise (``DataEntryEmissionService.
 * _get_year_from_data_entry``). Options and factor-seeded values have to follow
 * the same rule, or a form offers classes from one year while the emission is
 * computed with another year's factors.
 *
 * - ``undefined`` — Calculator: the report has no reference year, so its own
 *   year is the factor year.
 * - ``null`` — a Simulator Plan year with no reference year picked yet. There
 *   is no year to resolve against; callers must not fall back to the plan year,
 *   since the backend would not use it either.
 */
export function resolveFactorYear(
  factorYear: number | null | undefined,
  year: string | number | undefined,
): string | number | null | undefined {
  return factorYear === undefined ? year : factorYear;
}

/**
 * Mount key for a module's table, scoped to its factor year.
 *
 * `useEquipmentClassOptions` loads the class/subclass options once per mount —
 * it watches the submodule and the selected class, never the year. A new
 * factor year therefore only reaches the dropdowns by remounting the table,
 * which is what this key forces.
 */
export function factorMountKey(
  module: string,
  factorYear: number | null | undefined,
): string {
  return `${module}-${factorYear}`;
}
