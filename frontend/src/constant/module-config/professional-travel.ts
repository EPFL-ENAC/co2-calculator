import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';

const moduleFields: ModuleField[] = [
  {
    id: 'mode',
    label: 'Transport Mode',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'distance',
    label: 'Distance/Duration',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'co2Factor',
    label: 'CO₂ Factor',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'kg_co2eq',
    label: 'kg CO₂-éq',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'transport_car',
    label: 'Car Commuting (km/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
  {
    id: 'transport_public',
    label: 'Public Transport (km/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
  {
    id: 'transport_bike',
    label: 'Cycling (km/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
  {
    id: 'transport_flights',
    label: 'Business Flights (hours/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
];

export const professionalTravel: ModuleConfig = {
  id: 'module_transport_001',
  type: 'professional-travel',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  name: 'Employee Transportation',
  description: 'Track commuting and business travel emissions',
  hasSubmodules: false,
  formStructure: 'single',
  moduleFields,
};
