/**
 * Build select options from a year's factor catalog, for classifications
 * stored as opaque codes that need a separate field to display (#2007:
 * `researchfacility_id` 1902 reads as "SCITAS-GE").
 *
 * Store-free leaf so it stays unit-testable, like `dataEntryPolicy.ts`.
 */

export type FactorRow = Record<string, number | string | null>;
export type FactorOption = { label: string; value: string };

function present(raw: number | string | null | undefined): boolean {
  return raw !== null && raw !== undefined && raw !== '';
}

/**
 * One option per distinct `valueField`, labelled by `labelField`. A single
 * classification value can carry several factor rows — an animal facility has
 * one per housing type — and the select must still offer it once. Rows missing
 * either field are dropped: an unlabelled code is not a choosable option.
 */
export function toClassOptions(
  rows: FactorRow[],
  valueField: string,
  labelField: string,
): FactorOption[] {
  const byValue = new Map<string, string>();
  rows.forEach((row) => {
    const value = row[valueField];
    const label = row[labelField];
    if (!present(value) || !present(label)) return;
    if (!byValue.has(String(value))) byValue.set(String(value), String(label));
  });
  // Sorted by label: the catalog holds ~90 platforms and /list returns them in
  // DB order, while the class/subclass map this replaces was sorted server-side.
  return [...byValue]
    .map(([value, label]) => ({ label, value }))
    .sort((a, b) => a.label.localeCompare(b.label));
}
