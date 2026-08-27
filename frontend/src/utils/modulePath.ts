import { Module } from '@/constant/modules';

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
 * Single source of truth for `/carbon-reports/{id}/modules/{module}` paths
 * ("lookup once, then identity" — unit/year resolve to a report id once,
 * every module operation addresses the report directly).
 * Throws on a missing report id so a doomed request is never fired.
 */
export function buildModulePath(
  moduleType: Module,
  carbonReportId: number | null | undefined,
): string {
  if (carbonReportId == null || !Number.isFinite(carbonReportId)) {
    throw new Error(
      `buildModulePath: unresolved carbonReportId (${carbonReportId})`,
    );
  }
  return `carbon-reports/${encodeURIComponent(String(carbonReportId))}/modules/${encodeURIComponent(moduleType)}`;
}
