import { api } from '@/api/http';
import {
  CARBON_PROJECT,
  carbonReportLookupPath,
} from '@/constant/carbon-project';
import type { CarbonReport } from '@/stores/workspace';

/**
 * Start a new Simulator Explore sandbox (#2656).
 *
 * Always creates a fresh, empty sandbox — no idempotency, no "does this
 * exist" check. The backend deletes the caller's other sandboxes for this
 * unit in the background right after, so a page mount/refresh alike always
 * gets a clean slate; there's no "reuse the existing one" case any more.
 */
export async function postExploreCarbonReport(
  unitId: number,
  referenceYear: number,
): Promise<CarbonReport> {
  const path = carbonReportLookupPath(
    CARBON_PROJECT.explorer,
    unitId,
    referenceYear,
  );
  return api.post(path).json<CarbonReport>();
}

/**
 * Read the caller's current Simulator Explore sandbox (#2656) — 404 when none
 * exists. Read-only surfaces (the printable report) must use this: the POST
 * above always creates a fresh, empty sandbox and deletes the previous one,
 * so calling it to "load" an exploration destroys the exploration.
 */
export async function getExploreCarbonReport(
  unitId: number,
): Promise<CarbonReport> {
  const path = carbonReportLookupPath(CARBON_PROJECT.explorer, unitId, '');
  return api.get(path).json<CarbonReport>();
}
