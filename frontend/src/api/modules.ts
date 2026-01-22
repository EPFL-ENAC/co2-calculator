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
  const path = `modules/${unitEncoded}/${yearEncoded}/totals`;

  const response = await api.get(path).json<ModuleTotalsResponse>();
  return response;
}
