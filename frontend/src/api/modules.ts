import { api } from 'src/api/http';

/**
 * Response type for module totals endpoint
 * Keys are module names (e.g., "equipment-electric-consumption", "professional-travel")
 */
export interface ModuleTotalsResponse {
  total: number;
  'equipment-electric-consumption': number;
  'professional-travel': number;
  [key: string]: number; // Allow other module names as keys
}

/**
 * Fetch total tCO2eq for modules.
 *
 * @param unitId - Unit ID
 * @param year - Year for the data
 * @returns Dictionary with `total` tCO2eq and breakdown by module, including `equipment-electric-consumption` and `professional-travel`
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
 * Dropdown item returned by GET /modules/{unitId}/{year}/headcount/members.
 */
export interface HeadcountMemberDropdownItem {
  institutional_id: number;
  name: string;
}

/**
 * Fetch headcount members that have an institutional_id, for the traveler dropdown.
 *
 * @param unitId - Unit ID
 * @param year - Reporting year
 * @returns Ordered list of members with institutional_id and name
 */
export async function getHeadcountMembers(
  unitId: number,
  year: number | string,
): Promise<HeadcountMemberDropdownItem[]> {
  const unitEncoded = encodeURIComponent(unitId);
  const yearEncoded = encodeURIComponent(String(year));
  return api
    .get(`modules/${unitEncoded}/${yearEncoded}/headcount/members`)
    .json<HeadcountMemberDropdownItem[]>();
}

/**
 * Fetch the results summary for a carbon report.
 *
 * @param carbonReportId - Carbon report ID
 * @returns Unit-wide totals and per-module breakdowns
 */
export async function getResultsSummary(
  carbonReportId: number,
): Promise<ResultsSummary> {
  const path = `modules-stats/${encodeURIComponent(carbonReportId)}/results-summary`;
  return api.get(path).json<ResultsSummary>();
}
