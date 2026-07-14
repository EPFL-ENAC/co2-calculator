/**
 * Labels the perimeter of a report — which unit(s) it covers.
 *
 * Kept free of any i18n import (`t` is injected) so it stays usable from unit
 * specs: importing the i18n boot from a util pulls in `import.meta.glob` and
 * the spec silently collects no tests.
 */
export type TranslateFn = (
  key: string,
  named?: Record<string, unknown>,
) => string;

/** Up to two units in the perimeter are named; beyond that a counter is used. */
export function buildUnitPerimeterLabel(
  currentName: string,
  combinedNames: string[],
  t: TranslateFn,
): string {
  if (!combinedNames.length) return currentName;
  if (combinedNames.length === 1) return `${currentName} + ${combinedNames[0]}`;
  return t('results_combine_units_counter', {
    unit: currentName,
    count: combinedNames.length,
  });
}

/**
 * The perimeter of a backoffice export, which spans whatever the reporting
 * filters matched: a single unit, one whole affiliation, or a mixed bag.
 */
export function buildBackofficeScopeLabel(
  rows: Array<{ unit_name: string; affiliation: string }>,
  t: TranslateFn,
): string {
  if (rows.length === 1) return rows[0]?.unit_name ?? '';
  const affiliations = new Set(rows.map((row) => row.affiliation));
  if (affiliations.size === 1) {
    const [only] = [...affiliations];
    if (only) return only;
  }
  return t('print_scope_units_count', { count: rows.length });
}

/** Filename-safe version of a scope label, for `document.title`. */
export function toPrintDocumentTitle(scope: string, prefix: string): string {
  const slug = scope.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');
  return slug ? `${prefix}_${slug}` : prefix;
}
