import { MODULES } from 'src/constant/modules';
import { outlinedFolderShared } from '@quasar/extras/material-icons-outlined';

export type SubmoduleConfig = {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
  noData?: true;
  noFactors?: true;
  hasApi?: true;
  other?: string;
  isDisabled?: true;
  headerIcon?: string;
  descriptionKey?: string;
  factorsOnly?: true;
  mandatoryData?: boolean;
  mandatoryReference?: boolean;
  noThreshold?: true;
  forceInputsDeactivated?: true;
};

export const MODULE_SUBMODULES: Partial<
  Record<(typeof MODULES)[keyof typeof MODULES], SubmoduleConfig[]>
> = {
  [MODULES.Headcount]: [
    {
      key: 'member',
      labelKey: `${MODULES.Headcount}-member`,
      moduleTypeId: 1,
      dataEntryTypeId: 1,
      noThreshold: true,
    },
    {
      key: 'student',
      labelKey: `${MODULES.Headcount}-student`,
      moduleTypeId: 1,
      dataEntryTypeId: 2,
      noData: true,
      noThreshold: true,
    },
  ],
  [MODULES.ProfessionalTravel]: [
    {
      key: 'train',
      labelKey: `${MODULES.ProfessionalTravel}-train`,
      moduleTypeId: 2,
      dataEntryTypeId: 21,
      other: 'data_management_other_train_stations',
      mandatoryData: false,
      mandatoryReference: true,
    },
    {
      key: 'plane',
      labelKey: `${MODULES.ProfessionalTravel}-plane`,
      moduleTypeId: 2,
      dataEntryTypeId: 20,
      hasApi: true,
      other: 'data_management_other_airports',
      mandatoryData: false,
      mandatoryReference: true,
    },
  ],
  [MODULES.Buildings]: [
    {
      key: 'building',
      labelKey: `${MODULES.Buildings}-rooms`,
      moduleTypeId: 3,
      dataEntryTypeId: 30,
      other: 'data_management_other_institution_rooms',
      mandatoryData: false,
      mandatoryReference: true,
    },
    {
      key: 'energy_combustion',
      labelKey: `${MODULES.Buildings}-combustion`,
      moduleTypeId: 3,
      dataEntryTypeId: 31,
    },
    {
      key: 'building_embodied_energy',
      labelKey: 'data_management_submodule_buildings_construction_renovation',
      moduleTypeId: 3,
      dataEntryTypeId: 32,
      noData: true,
      factorsOnly: true,
    },
  ],
  [MODULES.ProcessEmissions]: [
    {
      key: 'process_emissions',
      labelKey: 'data_management_submodule_process_emissions',
      moduleTypeId: 8,
      dataEntryTypeId: 50,
    },
  ],
  [MODULES.Equipment]: [
    {
      key: 'scientific',
      labelKey: `${MODULES.Equipment}-scientific`,
      moduleTypeId: 4,
      dataEntryTypeId: 10,
      noData: true,
      noFactors: true,
    },
    {
      key: 'it',
      labelKey: `${MODULES.Equipment}-it`,
      moduleTypeId: 4,
      dataEntryTypeId: 11,
      noData: true,
      noFactors: true,
    },
    {
      key: 'other',
      labelKey: `${MODULES.Equipment}-other`,
      moduleTypeId: 4,
      dataEntryTypeId: 12,
      noData: true,
      noFactors: true,
    },
  ],
  [MODULES.Purchase]: [
    {
      key: 'scientific_equipment',
      labelKey: 'data_management_submodule_scientific_equipment',
      moduleTypeId: 5,
      dataEntryTypeId: 60,
      noData: true,
      noFactors: true,
    },
    {
      key: 'it_equipment',
      labelKey: 'data_management_submodule_it_equipment',
      moduleTypeId: 5,
      dataEntryTypeId: 61,
      noData: true,
      noFactors: true,
    },
    {
      key: 'consumable_accessories',
      labelKey: 'data_management_submodule_consumables_accessories',
      moduleTypeId: 5,
      dataEntryTypeId: 62,
      noData: true,
      noFactors: true,
    },
    {
      key: 'biological_chemical_gaseous_product',
      labelKey: 'data_management_submodule_bio_chemical_gaseous',
      moduleTypeId: 5,
      dataEntryTypeId: 63,
      noData: true,
      noFactors: true,
    },
    {
      key: 'services',
      labelKey: 'data_management_submodule_services',
      moduleTypeId: 5,
      dataEntryTypeId: 64,
      noData: true,
      noFactors: true,
    },
    {
      key: 'vehicles',
      labelKey: 'data_management_submodule_vehicles',
      moduleTypeId: 5,
      dataEntryTypeId: 65,
      noData: true,
      noFactors: true,
    },
    {
      key: 'other_purchases',
      labelKey: 'data_management_submodule_other_purchases',
      moduleTypeId: 5,
      dataEntryTypeId: 66,
      noData: true,
      noFactors: true,
    },
    {
      key: 'additional_purchases',
      labelKey: 'data_management_submodule_additional_purchases',
      moduleTypeId: 5,
      dataEntryTypeId: 67,
    },
  ],
  [MODULES.ResearchFacilities]: [
    {
      key: 'research-facilities',
      labelKey: 'data_management_submodule_research_facilities',
      moduleTypeId: 6,
      dataEntryTypeId: 70,
      forceInputsDeactivated: true,
    },
    {
      key: 'mice_and_fish_animal_facilities',
      labelKey: 'data_management_submodule_animal_facilities',
      moduleTypeId: 6,
      dataEntryTypeId: 71,
      forceInputsDeactivated: true,
    },
  ],
  [MODULES.ExternalCloudAndAI]: [
    {
      key: 'external_clouds',
      labelKey: `${MODULES.ExternalCloudAndAI}.cloud-services`,
      moduleTypeId: 7,
      dataEntryTypeId: 40,
    },
    {
      key: 'external_ai',
      labelKey: `${MODULES.ExternalCloudAndAI}.ai-services`,
      moduleTypeId: 7,
      dataEntryTypeId: 41,
    },
  ],
};

export const MODULE_COMMON_UPLOADS: Partial<
  Record<(typeof MODULES)[keyof typeof MODULES], SubmoduleConfig[]>
> = {
  [MODULES.Equipment]: [
    {
      key: 'equipment',
      labelKey: `${MODULES.Equipment}-common`,
      moduleTypeId: 4,
      headerIcon: outlinedFolderShared,
      descriptionKey: 'data_management_equipment_common_description',
    },
  ],
  [MODULES.Purchase]: [
    {
      key: 'purchases_common',
      labelKey: `${MODULES.Purchase}-common`,
      moduleTypeId: 5,
      headerIcon: outlinedFolderShared,
      descriptionKey: 'data_management_purchase_common_description',
    },
  ],
};
