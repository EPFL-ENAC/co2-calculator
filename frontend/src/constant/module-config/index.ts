import { ModuleConfig } from 'src/constant/moduleConfig';
import { equipmentElectricConsumption } from 'src/constant/module-config/equipment-electric-consumption';
import { professionalTravel } from 'src/constant/module-config/professional-travel';
import { headcount } from 'src/constant/module-config/headcount';
import { internalServices } from 'src/constant/module-config/internal-services';
import { externalCloudAndAi } from 'src/constant/module-config/external-cloud-and-ai';
import { infrastructure } from 'src/constant/module-config/infrastructure';
import { purchase } from 'src/constant/module-config/purchase';

export const MODULES_CONFIG: Record<string, ModuleConfig> = {
  'equipment-electric-consumption': equipmentElectricConsumption,
  'professional-travel': professionalTravel,
  headcount: headcount,
  'internal-services': internalServices,
  infrastructure: infrastructure,
  purchase: purchase,
  'external-cloud-and-ai': externalCloudAndAi,
};

export {
  equipmentElectricConsumption,
  professionalTravel,
  headcount,
  internalServices,
  infrastructure,
  purchase,
  externalCloudAndAi,
};
