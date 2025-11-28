import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.ProfessionalTravel]: {
    en: 'Professional Travel',
    fr: 'Professional Travel',
  },
  [MODULES_DESCRIPTIONS.ProfessionalTravel]: {
    en: 'Record team travel by plane and train with automatic CO₂ calculations',
    fr: 'Record team trips by plane and train with automatic CO₂ calculations',
  },
} as const;
