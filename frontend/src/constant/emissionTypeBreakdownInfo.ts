import type { Module } from 'src/constant/modules';
import { MODULES } from 'src/constant/modules';

/** i18n keys for the emission-type (stacked bar) chart explanatory tooltip. */
export const EMISSION_TYPE_BREAKDOWN_INFO_KEYS: Partial<
  Record<Module, string>
> = {
  [MODULES.EquipmentElectricConsumption]:
    'module-equipment-electric-consumption-charts',
  [MODULES.Buildings]: 'module-buildings-charts',
  [MODULES.ExternalCloudAndAI]: 'module-external-cloud-and-ai-charts',
  [MODULES.ResearchFacilities]: 'module-research-facilities-charts',
};

/** Returns the i18n message key for the module, or null when there is no copy. */
export function getEmissionTypeBreakdownInfoKey(
  module: Module | null | undefined,
): string | null {
  if (!module) return null;
  return EMISSION_TYPE_BREAKDOWN_INFO_KEYS[module] ?? null;
}
