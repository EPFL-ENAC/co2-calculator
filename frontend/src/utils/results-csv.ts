/**
 * Row building for the Results "empreinte carbone de l'unité" CSV export.
 *
 * Kept store-free and component-free so it stays importable by pure unit tests.
 */

/** One emission entry as the backend returns it inside a category row. */
export interface EmissionEntry {
  key: string;
  value: number;
  parent_key?: string;
}

/** A single CSV line: category > subcategory > subcategory2 = co2 (tonnes). */
export interface CarbonFootprintCsvRow {
  category: string;
  subcategory: string;
  subcategory2: string;
  co2: number;
}

/**
 * Build the export's rows from the chart's dataset rows.
 *
 * Each row is one *leaf* emission. Where the leaf has a parent (a travel class
 * under `train`/`plane`, a room type under `lighting`), the parent occupies the
 * subcategory column and the leaf the one after it. Two-level categories leave
 * `subcategory2` empty.
 *
 * This reads `emissions[]` rather than the row's flat numeric keys, because the
 * backend writes both a leaf (`class_2`) and its parent's sum (`train`) as
 * sibling flat keys — exporting those directly is what made the CSV read as a
 * jumble of same-level rows (#866). Only `emissions[]` carries `parent_key`.
 *
 * Subcategory columns carry the raw emission keys (`train`, `class_2`), not
 * localized labels — same as the flat keys the old export printed.
 *
 * @param entries Dataset rows (`category`, `category_key`, `emissions`, …).
 * @param isValidated Whether a category's data may be exported at all.
 */
export function buildCarbonFootprintCsvRows(
  entries: Array<Record<string, unknown>>,
  isValidated: (categoryKey: string) => boolean,
): CarbonFootprintCsvRow[] {
  return entries.flatMap((entry) => {
    const categoryKey = String(entry.category_key ?? '');
    // Non-validated categories keep real values in `emissions[]` — only their
    // flat numeric keys get zeroed upstream. Skip them, or the export leaks
    // data the chart itself refuses to draw.
    if (!isValidated(categoryKey)) return [];

    const category = String(entry.category ?? '');
    const emissions = Array.isArray(entry.emissions)
      ? (entry.emissions as EmissionEntry[])
      : [];

    return emissions.flatMap((emission) => {
      const co2 = Number(emission?.value);
      if (!Number.isFinite(co2) || co2 === 0) return [];

      const key = normalizeEmissionKey(categoryKey, emission.key);
      const parentKey = emission.parent_key;

      return [
        {
          category,
          subcategory: parentKey
            ? normalizeEmissionKey(categoryKey, parentKey)
            : key,
          subcategory2: parentKey ? key : '',
          co2,
        },
      ];
    });
  });
}

/**
 * Purchases name their catch-all bucket `other`, which is also equipment's
 * scientific/it/`other` key. Mirrors `normalizeCategoryRowKeys` in
 * `ModuleCarbonFootprintChart.vue` so both surfaces name it the same way.
 */
function normalizeEmissionKey(categoryKey: string, key: string): string {
  if (categoryKey === 'purchases' && key === 'other') return 'other_purchases';
  return key;
}
