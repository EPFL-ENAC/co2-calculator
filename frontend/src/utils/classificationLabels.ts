/**
 * Display label for a factor-sourced kind/subkind cell (#2401).
 *
 * The row's own backend-resolved label wins — purchase's localized
 * description rides each table row, so the huge purchase taxonomy is not
 * needed for display. Then the taxonomy label map (self-labeling modules,
 * whose tree the table already holds for its inline-edit options), then
 * the stored value itself (the English fallback by convention).
 */
export function kindCellLabel(
  rowLabels: Record<string, string> | null | undefined,
  field: string,
  taxonomyLabels: Record<string, string>,
  value: string,
): string {
  return rowLabels?.[field] ?? taxonomyLabels[value] ?? value;
}
