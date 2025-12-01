import { ModuleConfig } from 'src/constant/moduleConfig';

export const professionalTravel: ModuleConfig = {
  id: 'module_transport_001',
  type: 'professional-travel',
  name: 'Employee Transportation',
  description: 'Track commuting and business travel emissions',
  hasSubmodules: false,
  formStructure: 'single',
  formInputs: [
    {
      id: 'transport_car',
      label: 'Car Commuting (km/month)',
      type: 'number',
      required: true,
      min: 0,
    },
    {
      id: 'transport_public',
      label: 'Public Transport (km/month)',
      type: 'number',
      required: true,
      min: 0,
    },
    {
      id: 'transport_bike',
      label: 'Cycling (km/month)',
      type: 'number',
      required: true,
      min: 0,
    },
    {
      id: 'transport_flights',
      label: 'Business Flights (hours/month)',
      type: 'number',
      required: true,
      min: 0,
    },
  ],
  tableColumns: [
    { key: 'mode', label: 'Transport Mode', type: 'text', sortable: true },
    {
      key: 'distance',
      label: 'Distance/Duration',
      type: 'text',
      sortable: true,
    },
    { key: 'co2Factor', label: 'CO2 Factor', type: 'text', sortable: true },
    { key: 'kg_co2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
  ],
};
