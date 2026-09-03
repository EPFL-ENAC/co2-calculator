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
  factorYear: number | null,
): string {
  return `${module}-${factorYear}`;
}
