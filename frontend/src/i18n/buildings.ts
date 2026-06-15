import { MODULES } from 'src/constant/modules';

export default {
  [MODULES.Buildings]: {
    en: 'Buildings',
    fr: 'Bâtiments',
  },
  [`${MODULES.Buildings}-rooms`]: {
    en: 'Room | Rooms',
    fr: 'Local | Locaux',
  },
  [`${MODULES.Buildings}-description`]: {
    en: 'This module estimates the buildings-related carbon footprint (heating, air conditioning, ventilation, and lighting). An additional table is available to include other energy combustion sources if your unit uses a non-centralized energy source.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée au bâtiment (chauffage, climatisation, ventilation et éclairage). Un tableau supplémentaire est disponible pour compléter avec d'autres émissions de combustion d'énergie au cas où votre unité utilise une source d'énergie non-centralisée.",
  },
  [`${MODULES.Buildings}-title-subtext`]: {
    en: ' ',
    fr: ' ',
  },
  // Rooms submodule
  [`${MODULES.Buildings}.rooms_table_title`]: {
    en: 'Room ({count}) | Rooms ({count})',
    fr: 'Local ({count}) | Locaux ({count})',
  },
  [`${MODULES.Buildings}.add_room_button`]: {
    en: 'Add',
    fr: 'Ajouter',
  },
  [`${MODULES.Buildings}.rooms-form-title`]: {
    en: 'Add a room',
    fr: 'Ajouter un local',
  },
  [`${MODULES.Buildings}-rooms-form-add-info`]: {
    en: 'Please notify the Archibus administrator of any changes so that the data in Archibus can be updated and permanently reflected in the system.',
    fr: "Veuillez informer le gestionnaire d'Archibus de toute modification afin d'adapter les données dans Archibus pour qu'elles soient mises à jour de manière définitive dans le système.",
  },
  [`${MODULES.Buildings}-building-form-title`]: {
    en: 'Add a room',
    fr: 'Ajouter un local',
  },

  [`${MODULES.Buildings}-energy_combustion-form-title`]: {
    en: 'Add a heating type',
    fr: 'Ajouter un type de chauffage',
  },

  // Rooms fields
  [`${MODULES.Buildings}.inputs.building_name`]: {
    en: 'Building',
    fr: 'Bâtiment',
  },
  [`${MODULES.Buildings}.inputs.room_name`]: {
    en: 'Room',
    fr: 'Local',
  },
  [`${MODULES.Buildings}.inputs.room_type`]: {
    en: 'Type',
    fr: 'Type',
  },
  [`${MODULES.Buildings}.room_type.Office`]: {
    en: 'Office',
    fr: 'Bureau',
  },
  [`${MODULES.Buildings}.room_type.Miscels`]: {
    en: 'Miscellaneous',
    fr: 'Divers',
  },
  [`${MODULES.Buildings}.room_type.Laboratories`]: {
    en: 'Laboratory',
    fr: 'Laboratoire',
  },
  [`${MODULES.Buildings}.room_type.Archives`]: {
    en: 'Archives',
    fr: 'Archives',
  },
  [`${MODULES.Buildings}.room_type.Libraries`]: {
    en: 'Library',
    fr: 'Bibliothèque',
  },
  [`${MODULES.Buildings}.room_type.Auditoriums`]: {
    en: 'Auditorium',
    fr: 'Auditoires',
  },
  [`${MODULES.Buildings}.inputs.room_surface_square_meter`]: {
    en: 'Surface (m²)',
    fr: 'Surface (m²)',
  },
  [`${MODULES.Buildings}.inputs.room_allocation_ratio`]: {
    en: 'Allocation ratio',
    fr: 'Ratio alloué',
  },
  [`${MODULES.Buildings}.inputs.heating_kwh_per_square_meter`]: {
    en: 'Heating (kWh/m²)',
    fr: 'Chauffage (kWh/m²)',
  },
  [`${MODULES.Buildings}.inputs.cooling_kwh_per_square_meter`]: {
    en: 'Cooling (kWh/m²)',
    fr: 'Refroidissement (kWh/m²)',
  },
  [`${MODULES.Buildings}.inputs.ventilation_kwh_per_square_meter`]: {
    en: 'Ventilation (kWh/m²)',
    fr: 'Ventilation (kWh/m²)',
  },
  [`${MODULES.Buildings}.inputs.lighting_kwh_per_square_meter`]: {
    en: 'Lighting (kWh/m²)',
    fr: 'Éclairage (kWh/m²)',
  },
  [`${MODULES.Buildings}.inputs.heating_kwh`]: {
    en: 'Heating (kWh)',
    fr: 'Chauffage (kWh)',
  },
  [`${MODULES.Buildings}.inputs.cooling_kwh`]: {
    en: 'Cooling (kWh)',
    fr: 'Refroidissement (kWh)',
  },
  [`${MODULES.Buildings}.inputs.ventilation_kwh`]: {
    en: 'Ventilation (kWh)',
    fr: 'Ventilation (kWh)',
  },
  [`${MODULES.Buildings}.inputs.lighting_kwh`]: {
    en: 'Lighting (kWh)',
    fr: 'Éclairage (kWh)',
  },

  // Energy combustion submodule
  [`${MODULES.Buildings}-combustion`]: {
    en: 'Energy Combustion Emissions | Energy Combustions Emissions',
    fr: "Émissions de combustion d'énergie | Émissions de combustion d'énergie ",
  },
  [`${MODULES.Buildings}.combustion_table_title`]: {
    en: 'Energy Combustion Emissions ({count}) | Energy Combustions Emissions ({count})',
    fr: "Émissions de combustion d'énergie ({count}) | Émissions de combustion d'énergie ({count})",
  },
  [`${MODULES.Buildings}.add_combustion_button`]: {
    en: 'Add',
    fr: 'Ajouter ',
  },
  [`${MODULES.Buildings}.combustion-form-title`]: {
    en: 'Add a heating type',
    fr: 'Ajouter un type de chauffage',
  },

  // Combustion fields
  [`${MODULES.Buildings}.inputs.name`]: {
    en: 'Heating type',
    fr: 'Type de chauffage',
  },
  [`${MODULES.Buildings}.inputs.unit`]: {
    en: 'Unit',
    fr: 'Unité',
  },
  [`${MODULES.Buildings}.inputs.quantity`]: {
    en: 'Quantity',
    fr: 'Quantité',
  },

  // Combustion type options (stored as translation keys in factor data)
  natural_gas: {
    en: 'Natural gas',
    fr: 'Gaz naturel',
  },
  heating_oil: {
    en: 'Heating oil',
    fr: 'Mazout',
  },
  biomethane: {
    en: 'Biomethane',
    fr: 'Biométhane',
  },
  propane: {
    en: 'Propane',
    fr: 'Propane',
  },
  pellets: {
    en: 'Pellets',
    fr: 'Granulés de bois',
  },
  forest_chips: {
    en: 'Forest chips',
    fr: 'Plaquettes forestières',
  },
  wood_logs: {
    en: 'Wood logs',
    fr: 'Bois bûche',
  },

  // Charts
  [`${MODULES.Buildings}-charts-title`]: {
    en: 'Buildings Charts',
    fr: 'Graphiques des bâtiments',
  },
  [`${MODULES.Buildings}-charts-no-data-message`]: {
    en: 'No buildings data available.',
    fr: 'Aucune donnée de bâtiment disponible.',
  },

  // Status
  [`${MODULES.Buildings}.work_in_progress`]: {
    en: 'work in progress, please validate to confirm your entries',
    fr: "en cours jusqu'à validation de vos entrées",
  },
  'buildings-room-type-office': {
    en: 'Office',
    fr: 'Bureau',
  },
  'buildings-room-type-miscellaneous': {
    en: 'Miscellaneous',
    fr: 'Divers',
  },
  'buildings-room-type-laboratories': {
    en: 'Laboratories',
    fr: 'Laboratoires',
  },
  'buildings-room-type-archives': {
    en: 'Archives',
    fr: 'Archives',
  },
  'buildings-room-type-libraries': {
    en: 'Libraries',
    fr: 'Bibliothèques',
  },
  'buildings-room-type-auditoriums': {
    en: 'Auditoriums',
    fr: 'Auditoires',
  },
} as const;
