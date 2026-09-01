/**
 * Display label for a factor-sourced kind/subkind cell (#2401).
 *
 * The taxonomy label map wins when the tree is held (self-labeling
 * modules and research facilities keep their exact pre-#2401 rendering,
 * including the `$te` enum-key branch some modules rely on); the row's
 * backend-resolved label is the source for modules that no longer fetch
 * the tree (purchase — its map is empty); the stored value is the English
 * fallback by convention.
 */
export function kindCellLabel(
  rowLabels: Record<string, string> | null | undefined,
  field: string,
  taxonomyLabels: Record<string, string>,
  value: string,
): string {
  return taxonomyLabels[value] ?? rowLabels?.[field] ?? value;
}
