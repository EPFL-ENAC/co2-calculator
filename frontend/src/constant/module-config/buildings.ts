import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_BUILDINGS_TYPES, MODULES } from 'src/constant/modules';
import type {
  BuildingsSubType,
  Module,
  TaxonomyNode,
} from 'src/constant/modules';
import { formatTonnesCO2 } from 'src/utils/number';
import type { AllSubmoduleTypes } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useBuildingRoomStore } from 'src/stores/building_rooms';

const buildingRoomStore = useBuildingRoomStore();
const moduleStore = useModuleStore();

/**
 * Room characteristics (surface, default type) are fetched on demand.
 * @param subModuleType
 * @param entry
 * @returns
 */
async function getRoom(
  subModuleType: AllSubmoduleTypes,
  entry: Record<string, unknown>,
) {
  if (!entry) return null;
  const buildingName = entry['building_name'];
  if (typeof buildingName !== 'string') return null;
  const roomName = entry['room_name'];
  if (typeof roomName !== 'string') return null;
  const rooms = await buildingRoomStore.fetchRooms(buildingName);
  if (!rooms || rooms.length === 0) return null;
  return rooms.find((r) => r.room_name === roomName);
}

/**
 * Get the taxonomy node from the selected building name.
 * @param subModuleType
 * @param entry
 * @returns
 */
function getBuildingNode(
  subModuleType: AllSubmoduleTypes,
  entry: Record<string, unknown>,
): TaxonomyNode | null {
  if (!entry) return null;
  const buildingName = entry['building_name'];
  if (typeof buildingName !== 'string') return null;
  const roomType = entry['room_type'];
  if (typeof roomType !== 'string') return null;
  const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
  if (!taxoNode || !taxoNode.children) return null;
  const buildingNode = taxoNode.children.find(
    (child) => child.name === buildingName,
  );
  return buildingNode;
}

/**
 * Factor values are stored in the taxonomy under the room type node, so we need
 * to navigate there to get them.
 * @param subModuleType
 * @param entry
 * @returns
 */
function getRoomValues(
  subModuleType: AllSubmoduleTypes,
  entry: Record<string, unknown>,
) {
  if (!entry) return {};
  const roomType = entry['room_type'];
  if (typeof roomType !== 'string') return {};
  const buildingNode = getBuildingNode(subModuleType, entry);
  if (!buildingNode || !buildingNode.children) return {};
  const roomTypeNode = buildingNode.children.find(
    (child) => child.name === roomType,
  );
  if (!roomTypeNode) return {};
  return roomTypeNode.values || {};
}

const roomFields: ModuleField[] = [
  {
    id: 'building_name',
    optionsId: 'kind',
    labelKey: `${MODULES.Buildings}.inputs.building_name`,
    type: 'select',
    required: true,
    sortable: true,
    editableInline: false,
    inputTypeName: 'QSelect',
    align: 'left',
    ratio: '1/3',
    icon: 'o_apartment',
    optionsFunction: async (subModuleType, entry) => {
      if (!entry) return [];
      const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
      if (!taxoNode || !taxoNode.children) return [];
      return taxoNode.children.map((child) => ({
        value: child.name,
        label: child.label,
      }));
    },
  },
  {
    id: 'room_name',
    labelKey: `${MODULES.Buildings}.inputs.room_name`,
    type: 'select',
    required: true,
    sortable: true,
    editableInline: false,
    inputTypeName: 'QSelect',
    align: 'left',
    ratio: '1/3',
    icon: 'o_meeting_room',
    optionsFunction: async (subModuleType, entry) => {
      if (!entry) return [];
      if (entry['building_name'] === null) return [];
      const buildingName = entry['building_name'];
      if (typeof buildingName !== 'string') return [];
      const rooms = await buildingRoomStore.fetchRooms(buildingName);
      if (!rooms) return [];
      return rooms.map((room) => ({
        value: room.room_name,
        label: room.room_name,
      }));
    },
    disable: (subModuleType, entry) => {
      return !entry['building_name'];
    },
  },
  {
    id: 'room_type',
    labelKey: `${MODULES.Buildings}.inputs.room_type`,
    type: 'select',
    sortable: true,
    editableInline: true,
    inputTypeName: 'QSelect',
    align: 'left',
    ratio: '1/3',
    icon: 'o_category',
    // IMPORTANT: these values are backend emission-factor lookup keys.
    // Do not translate or rename without matching backend seed/data updates.
    // See: https://github.com/EPFL-ENAC/co2-calculator/issues/173
    optionsFunction: async (subModuleType, entry) => {
      console.log('Fetching room type options'); // Debug log
      const buildingNode = getBuildingNode(subModuleType, entry);
      if (!buildingNode || !buildingNode.children) return [];
      const roomTypes = buildingNode.children.map((child) => ({
        value: child.name,
        label: child.label,
      }));
      return roomTypes;
    },
    default: async (subModuleType, entry) => {
      const room = await getRoom(subModuleType, entry);
      console.log('Fetched room for default room type:', room);
      return room?.room_type ?? null;
    },
    disable: (subModuleType, entry) => {
      return !entry['room_name'];
    },
  },
  {
    id: 'room_surface_square_meter',
    labelKey: `${MODULES.Buildings}.inputs.room_surface_square_meter`,
    type: 'number',
    sortable: true,
    editableInline: false,
    readOnlyWhenFilled: true,
    unit: 'm²',
    ratio: '1/5',
    icon: 'o_straighten',
    default: async (subModuleType, entry) => {
      const room = await getRoom(subModuleType, entry);
      return room?.room_surface_square_meter ?? null;
    },
    disable: (subModuleType, entry) => {
      return !entry['room_name'];
    },
  },
  {
    id: 'heating_kwh_per_square_meter',
    labelKey: `${MODULES.Buildings}.inputs.heating_kwh_per_square_meter`,
    type: 'number',
    readOnlyWhenFilled: true,
    sortable: false,
    unit: 'kWh/m²',
    ratio: '1/5',
    icon: 'o_thermostat',
    tooltip: `${MODULES.Buildings}.tooltips.heating`,
    default: async (subModuleType, entry) => {
      const roomValue = getRoomValues(subModuleType, entry);
      return roomValue['heating_kwh_per_square_meter'] as number | null;
    },
    disable: (subModuleType, entry) => {
      return !entry['room_name'];
    },
  },
  {
    id: 'cooling_kwh_per_square_meter',
    labelKey: `${MODULES.Buildings}.inputs.cooling_kwh_per_square_meter`,
    type: 'number',
    readOnlyWhenFilled: true,
    sortable: false,
    unit: 'kWh/m²',
    ratio: '1/5',
    icon: 'o_ac_unit',
    tooltip: `${MODULES.Buildings}.tooltips.cooling`,
    default: async (subModuleType, entry) => {
      const roomValue = getRoomValues(subModuleType, entry);
      return roomValue['cooling_kwh_per_square_meter'] as number | null;
    },
    disable: (subModuleType, entry) => {
      return !entry['room_name'];
    },
  },
  {
    id: 'ventilation_kwh_per_square_meter',
    labelKey: `${MODULES.Buildings}.inputs.ventilation_kwh_per_square_meter`,
    type: 'number',
    readOnlyWhenFilled: true,
    sortable: false,
    unit: 'kWh/m²',
    ratio: '1/5',
    icon: 'o_air',
    tooltip: `${MODULES.Buildings}.tooltips.ventilation`,
    default: async (subModuleType, entry) => {
      const roomValue = getRoomValues(subModuleType, entry);
      return roomValue['ventilation_kwh_per_square_meter'] as number | null;
    },
    disable: (subModuleType, entry) => {
      return !entry['room_name'];
    },
  },
  {
    id: 'lighting_kwh_per_square_meter',
    labelKey: `${MODULES.Buildings}.inputs.lighting_kwh_per_square_meter`,
    type: 'number',
    readOnlyWhenFilled: true,
    sortable: false,
    unit: 'kWh/m²',
    ratio: '1/5',
    icon: 'o_light_mode',
    tooltip: `${MODULES.Buildings}.tooltips.lighting`,
    default: async (subModuleType, entry) => {
      const roomValue = getRoomValues(subModuleType, entry);
      return roomValue['lighting_kwh_per_square_meter'] as number | null;
    },
    disable: (subModuleType, entry) => {
      return !entry['room_name'];
    },
  },
  {
    id: 'kg_co2eq',
    labelKey: 'results_units_kg',
    type: 'number',
    readOnly: true,
    hideIn: { form: true },
    sortable: true,
  },
];

/**
 * Get the factor values for a given combustion type from the taxonomy.
 * @param subModuleType
 * @param entry
 * @returns
 */
function getEnergyCombustionValues(
  subModuleType: AllSubmoduleTypes,
  entry: Record<string, unknown>,
) {
  if (!entry) return {};
  const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
  if (!taxoNode || !taxoNode.children) return {};
  const combustionNode = taxoNode.children.find(
    (child) => child.name === entry['heating_type'],
  );
  if (!combustionNode) return {};
  return combustionNode.values || {};
}

const energyCombustionFields: ModuleField[] = [
  {
    id: 'heating_type',
    optionsId: 'kind',
    labelKey: `${MODULES.Buildings}.inputs.heating_type`,
    type: 'select',
    required: true,
    sortable: true,
    editableInline: true,
    inputTypeName: 'QSelect',
    align: 'left',
    ratio: '1/3',
    icon: 'o_local_fire_department',
    hideIn: { form: false },
  },
  {
    id: 'unit',
    labelKey: `${MODULES.Buildings}.inputs.unit`,
    type: 'text',
    readOnlyWhenFilled: true,
    sortable: false,
    align: 'left',
    ratio: '1/3',
    hideIn: { form: false },
    default: async (subModuleType, entry) => {
      return (
        (getEnergyCombustionValues(subModuleType, entry)['unit'] as string) ??
        null
      );
    },
  },
  {
    id: 'quantity',
    labelKey: `${MODULES.Buildings}.inputs.quantity`,
    type: 'number',
    required: true,
    editableInline: true,
    sortable: true,
    min: 0.001,
    step: 0.001,
    ratio: '1/3',
    hideIn: { form: false },
  },
  {
    id: 'kg_co2eq',
    labelKey: 'results_units_kg',
    type: 'number',
    readOnly: true,
    hideIn: { form: true },
    sortable: true,
  },
];

export const buildings: ModuleConfig = {
  id: 'module_buildings_001',
  type: MODULES.Buildings as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description:
    'Estimate building-related carbon footprint from energy consumption and combustion',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  numberFormatOptions: {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  },
  submodules: [
    {
      id: SUBMODULE_BUILDINGS_TYPES.Building,
      type: SUBMODULE_BUILDINGS_TYPES.Building as AllSubmoduleTypes,
      tableNameKey: `${MODULES.Buildings}.rooms_table_title`,
      moduleFields: roomFields,
      hasTableAction: true,
      addButtonLabelKey: `${MODULES.Buildings}.add_room_button`,
    },
    {
      id: SUBMODULE_BUILDINGS_TYPES.EnergyCombustion,
      type: SUBMODULE_BUILDINGS_TYPES.EnergyCombustion as BuildingsSubType,
      tableNameKey: `${MODULES.Buildings}.combustion_table_title`,
      moduleFields: energyCombustionFields,
      hasTableAction: true,
      hasFormTooltip: `${MODULES.Buildings}-energy_combustion-form-title-info-tooltip`,
      addButtonLabelKey: `${MODULES.Buildings}.add_combustion_button`,
    },
  ],
  totalFormatter: formatTonnesCO2,
};
