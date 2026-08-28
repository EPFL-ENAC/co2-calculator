import { api } from '@/api/http';
import {
  CARBON_PROJECT,
  carbonReportLookupPath,
} from '@/constant/carbon-project';
import type { CarbonReport } from '@/stores/workspace';

/**
 * Idempotent Simulator Explore sandbox (#2487): creates it on the unit/
 * user's first call, returns the existing one on every call after —
 * creating project/report/modules server-side, never a client 404 branch.
 *
 * Replaces the GET(404) + POST pair `workspace.ts` used to orchestrate:
 * two round trips, and the 404-as-control-flow race #2483 had to
 * SAVEPOINT-guard. Call unconditionally; there is no "not found" case.
 */
export async function putExploreCarbonReport(
  unitId: number,
  referenceYear: number,
): Promise<CarbonReport> {
  const path = carbonReportLookupPath(
    CARBON_PROJECT.explorer,
    unitId,
    referenceYear,
  );
  return api.put(path).json<CarbonReport>();
}
