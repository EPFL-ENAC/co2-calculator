import { ModuleConfig } from '@/constant/moduleConfig';
import { equipment } from '@/constant/module-config/equipment';
import { professionalTravel } from '@/constant/module-config/professional-travel';
import { headcount } from '@/constant/module-config/headcount';
import { researchFacilities } from '@/constant/module-config/research-facilities';
import { externalCloudAndAi } from '@/constant/module-config/external-cloud-and-ai';
import { buildings } from '@/constant/module-config/buildings';
import { purchase } from '@/constant/module-config/purchase';
import { processEmissions } from '@/constant/module-config/process_emissions';
import { MODULES } from '@/constant/modules';

export const MODULES_CONFIG: Record<string, ModuleConfig> = {
  [MODULES.Equipment]: equipment,
  [MODULES.ProfessionalTravel]: professionalTravel,
  [MODULES.Headcount]: headcount,
  [MODULES.ResearchFacilities]: researchFacilities,
  [MODULES.Buildings]: buildings,
  [MODULES.Purchase]: purchase,
  [MODULES.ExternalCloudAndAI]: externalCloudAndAi,
  [MODULES.ProcessEmissions]: processEmissions,
};

export {
  equipment,
  professionalTravel,
  headcount,
  researchFacilities,
  buildings,
  purchase,
  externalCloudAndAi,
  processEmissions,
};
