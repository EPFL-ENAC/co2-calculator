import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.MyLab]: {
    en: 'My Lab',
    fr: 'My Laboratory',
  },
  [MODULES_DESCRIPTIONS.MyLab]: {
    en: 'Enter personnel headcount and FTE values to establish your lab profile',
    fr: 'Enter staff and FTEs to establish your laboratory profile',
  },
} as const;
