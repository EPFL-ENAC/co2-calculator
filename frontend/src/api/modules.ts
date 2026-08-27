import { api } from '@/api/http';

/**
 * Response type for module totals endpoint
 * Keys are module names (e.g., "equipment", "professional-travel")
 */
export interface ModuleTotalsResponse {
  total: number;
  equipment: number;
  'professional-travel': number;
  [key: string]: number; // Allow other module names as keys
}

/**
 * Fetch total tCO₂eq for modules.
 *
 * @param unitId - Unit ID
 * @param year - Year for the data
 * @returns Dictionary with `total` tCO₂eq and breakdown by module, including `equipment` and `professional-travel`
 */
export async function getModuleTotals(
  unitId: number,
  year: number | string,
): Promise<ModuleTotalsResponse> {
  const unitEncoded = encodeURIComponent(unitId);
  const yearEncoded = encodeURIComponent(String(year));
  const path = `modules-stats/${unitEncoded}/${yearEncoded}/totals`;

  const response = await api.get(path).json<ModuleTotalsResponse>();
  return response;
}

/**
 * Per-module result in the results summary response.
 */
export interface ModuleResult {
  module_type_id: number;
  total_tonnes_co2eq: number;
  total_fte: number | null;
  tonnes_co2eq_per_fte: number | null;
  equivalent_car_km: number;
  previous_year_total_tonnes_co2eq: number | null;
  year_comparison_percentage: number | null;
}

/**
 * Response type for the results-summary endpoint.
 */
export interface ResultsSummary {
  unit_totals: {
    total_tonnes_co2eq: number | null;
    total_fte: number | null;
    tonnes_co2eq_per_fte: number | null;
    equivalent_car_km: number | null;
    previous_year_total_tonnes_co2eq: number | null;
    year_comparison_percentage: number | null;
  };
  co2_per_km_kg: number;
  module_results: ModuleResult[];
}

/**
 * Dropdown item returned by
 * GET /carbon-reports/{carbonReportId}/modules/headcount/members.
 */
export interface HeadcountMemberDropdownItem {
  institutional_id: string;
  name: string;
}

// Concurrent mount-time callers (travel tables, traveler selects, charts)
// share one request per report (4 identical GETs observed on explore-page
// mount, #2360). Only the in-flight promise is held — never the result — so
// later calls refetch and see roster edits.
const headcountMembersInFlight = new Map<
  number,
  Promise<HeadcountMemberDropdownItem[]>
>();

/**
 * Fetch headcount members that have an institutional_id, for the traveler dropdown.
 *
 * @param carbonReportId - The addressed carbon report (pins unit and year;
 *   resolve it via moduleStore.resolveCarbonReportId)
 * @returns Ordered list of members with institutional_id and name
 */
export async function getHeadcountMembers(
  carbonReportId: number,
): Promise<HeadcountMemberDropdownItem[]> {
  const inFlight = headcountMembersInFlight.get(carbonReportId);
  if (inFlight) return inFlight;
  const request = api
    .get(
      `carbon-reports/${encodeURIComponent(String(carbonReportId))}/modules/headcount/members`,
    )
    .json<HeadcountMemberDropdownItem[]>()
    .finally(() => headcountMembersInFlight.delete(carbonReportId));
  headcountMembersInFlight.set(carbonReportId, request);
  return request;
}

/**
 * Fetch the results summary for a carbon report.
 *
 * @param carbonReportId - Carbon report ID
 * @param excludeModules - Optional list of module_type_ids to exclude from totals
 * @returns Unit-wide totals and per-module breakdowns
 */
export async function getResultsSummary(
  carbonReportId: number,
  excludeModules: number[] = [],
): Promise<ResultsSummary> {
  const path = `modules-stats/${encodeURIComponent(carbonReportId)}/results-summary`;
  const searchParams = new URLSearchParams();
  for (const id of excludeModules) {
    searchParams.append('exclude_modules', String(id));
  }
  const query = searchParams.toString();
  return api.get(query ? `${path}?${query}` : path).json<ResultsSummary>();
}

/**
 * Fetch the results summary summed over several units for one year.
 *
 * @param unitIds - Units to combine, including the one currently viewed
 * @param year - Report year
 * @param excludeModules - Optional list of module_type_ids to exclude from totals
 * @returns Combined totals and per-module breakdowns, same shape as the single-unit call
 */
export async function getMergedResultsSummary(
  unitIds: number[],
  year: number,
  excludeModules: number[] = [],
): Promise<ResultsSummary> {
  const searchParams = new URLSearchParams();
  searchParams.append('year', String(year));
  for (const id of unitIds) {
    searchParams.append('unit_ids', String(id));
  }
  for (const id of excludeModules) {
    searchParams.append('exclude_modules', String(id));
  }
  return api
    .get(`modules-stats/merged/results-summary?${searchParams.toString()}`)
    .json<ResultsSummary>();
}
