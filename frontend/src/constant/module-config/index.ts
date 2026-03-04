import { ModuleConfig } from 'src/constant/moduleConfig';
import { equipmentElectricConsumption } from 'src/constant/module-config/equipment-electric-consumption';
import { professionalTravel } from 'src/constant/module-config/professional-travel';
import { headcount } from 'src/constant/module-config/headcount';
import { internalServices } from 'src/constant/module-config/internal-services';
import { externalCloudAndAi } from 'src/constant/module-config/external-cloud-and-ai';
import { buildings } from 'src/constant/module-config/buildings';
import { purchase } from 'src/constant/module-config/purchase';
import { processEmissions } from 'src/constant/module-config/process_emissions';

export const MODULES_CONFIG: Record<string, ModuleConfig> = {
  'equipment-electric-consumption': equipmentElectricConsumption,
  'professional-travel': professionalTravel,
  headcount: headcount,
  'internal-services': internalServices,
  buildings: buildings,
  purchase: purchase,
  'external-cloud-and-ai': externalCloudAndAi,
  'process-emissions': processEmissions,
};

export {
  equipmentElectricConsumption,
  professionalTravel,
  headcount,
  internalServices,
  buildings,
  purchase,
  externalCloudAndAi,
  processEmissions,
};
