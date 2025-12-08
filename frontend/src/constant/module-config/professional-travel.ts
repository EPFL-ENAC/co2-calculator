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
    label: 'kg CO₂-eq',
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
  uncertainty: 'low',
  formStructure: 'single',
  moduleFields,
  tableColumns: [
    { id: 'mode', label: 'Transport Mode', type: 'text', sortable: true },
    {
      id: 'distance',
      label: 'Distance/Duration',
      type: 'text',
      sortable: true,
    },
    { id: 'co2Factor', label: 'CO2 Factor', type: 'text', sortable: true },
    { id: 'kg_co2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
  ],
  resultBigNumbers: [
    {
      titleKey: 'professional-travel-results-total-travel-carbon-footprint',
      numberKey: 'total_travel_carbon_footprint',
      comparisonKey:
        'professional-travel-results-total-travel-carbon-footprint-comparison',
      comparisonParams: { km: "10'000" },
      comparisonHighlight: "10'000",
      color: 'negative',
      tooltipKey:
        'professional-travel-results-total-travel-carbon-footprint-tooltip',
    },
    {
      titleKey: 'professional-travel-results-travel-per-fte',
      numberKey: 'travel_per_fte',
      unitKey: 'professional-travel-results-travel-per-fte-unit',
      comparisonKey: 'professional-travel-results-travel-per-fte-comparison',
      comparisonParams: { percentage: '28%' },
      comparisonHighlight: '28%',
      color: 'negative',
      tooltipKey: 'professional-travel-results-travel-per-fte-tooltip',
    },
    {
      titleKey: 'professional-travel-results-year-to-year-evolution',
      numberKey: 'year_to_year_evolution',
      comparisonKey:
        'professional-travel-results-year-to-year-evolution-comparison',
      comparisonParams: { trips: '3' },
      comparisonHighlight: '3 trips',
      color: 'positive',
      tooltipKey: 'professional-travel-results-year-to-year-evolution-tooltip',
    },
  ],
};
