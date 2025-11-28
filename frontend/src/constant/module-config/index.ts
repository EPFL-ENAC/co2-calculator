import { ModuleConfig } from 'src/constant/moduleConfig';
import { equipmentElectricConsumption } from 'src/constant/module-config/equipment-electric-consumption';
import { professionalTravel } from 'src/constant/module-config//professional-travel';
import { myLab } from 'src/constant/module-config/my-lab';
import { internalServices } from 'src/constant/module-config/internal-services';
import { externalCloud } from 'src/constant/module-config/external-cloud';
import { infrastructure } from 'src/constant/module-config/infrastructure';
import { purchase } from 'src/constant/module-config/purchase';

export const MODULES_CONFIG: Record<string, ModuleConfig> = {
  'equipment-electric-consumption': equipmentElectricConsumption,
  'professional-travel': professionalTravel,
  'my-lab': myLab,
  'internal-services': internalServices,
  infrastructure: infrastructure,
  purchase: purchase,
  'external-cloud': externalCloud,
};

export {
  equipmentElectricConsumption,
  professionalTravel,
  myLab,
  internalServices,
  infrastructure,
  purchase,
  externalCloud,
};
