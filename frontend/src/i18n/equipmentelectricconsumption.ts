import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
    [MODULES.EquipmentElectricConsumption]: {
        en: 'Equipments',
        fr: 'Equipment Electricity Consumption',
    },
    [MODULES_DESCRIPTIONS.EquipmentElectricConsumption]: {
        en: 'List lab equipment with wattage to calculate electricity-related CO₂',
        fr: 'List laboratory equipment with their power to calculate CO₂ related to electricity',
    },
} as const;
