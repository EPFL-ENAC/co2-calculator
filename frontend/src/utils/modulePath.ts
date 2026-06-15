import { Module } from 'src/constant/modules';

/**
 * Values produced when a Vue ref is stringified before it has resolved
 * (`String(undefined)` / `String(null)`). The backend treats `{unit_id}`
 * and `{year}` as ints, so these literals reach it as path segments and
 * trigger a 422 — see the `modules/undefined/null/...` bug.
 */
const UNRESOLVED = new Set(['', 'undefined', 'null', 'NaN']);

/** True when both unit and year are present and not unresolved placeholders. */
export function hasValidModuleParams(
  unit: number | string | null | undefined,
  year: string | number | null | undefined,
): boolean {
  if (unit == null || year == null) return false;
  return !UNRESOLVED.has(String(unit)) && !UNRESOLVED.has(String(year));
}

/**
 * Single source of truth for `/modules/{unit}/{year}/{module}` paths.
 * Throws on missing/unresolved params so a doomed request is never fired
 * with `undefined`/`null` segments.
 */
export function buildModulePath(
  moduleType: Module,
  unit: number | string | null | undefined,
  year: string | number | null | undefined,
): string {
  if (!hasValidModuleParams(unit, year)) {
    throw new Error(
      `buildModulePath: unresolved unit/year (unit=${unit}, year=${year})`,
    );
  }
  return `modules/${encodeURIComponent(String(unit))}/${encodeURIComponent(
    String(year),
  )}/${encodeURIComponent(moduleType)}`;
}
