import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.Buildings]: {
    en: 'Buildings',
    fr: 'Bâtiments',
  },
  [MODULES_DESCRIPTIONS.Buildings]: {
    en: 'This module estimates the buildings-related carbon footprint (heating, air conditioning, ventilation, and lighting). An additional table is available to include other energy combustion sources if your unit uses a non-centralized energy source.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée au bâtiment (chauffage, climatisation, ventilation et éclairage). Un tableau supplémentaire est disponible pour compléter avec d'autres émissions de combustion d'énergie au cas où votre unité utilise une source d'énergie non-centralisée.",
  },
  [`${MODULES.Buildings}-title-subtext`]: {
    en: ' ',
    fr: ' ',
  },
  [`${MODULES.Buildings}-title-tooltip-title`]: {
    en: ' ',
    fr: ' ',
  },

  // Rooms submodule
  [`${MODULES.Buildings}.rooms_table_title`]: {
    en: 'Room ({count}) | Rooms ({count})',
    fr: 'Local ({count}) | Locaux ({count})',
  },
  [`${MODULES.Buildings}.add_room_button`]: {
    en: 'Add a room',
    fr: 'Ajouter un local',
  },
  [`${MODULES.Buildings}.rooms-form-title`]: {
    en: 'Add a room',
    fr: 'Ajouter un local',
  },
  [`${MODULES.Buildings}-building-form-title`]: {
    en: 'Add a room',
    fr: 'Ajouter un local',
  },
  [`${MODULES.Buildings}-building-form-title-info-label`]: {
    en: 'Information about adding a room',
    fr: "Information sur l'ajout d'un local",
  },
  [`${MODULES.Buildings}-energy_combustion-form-title`]: {
    en: 'Add an energy source',
    fr: "Ajouter une source d'énergie",
  },
  [`${MODULES.Buildings}-energy_combustion-form-tooltip`]: {
    en: 'Enter the sources of fossil or non-fossil energy combustion if they are not taken into account in the main module.',
    fr: 'Entrez les sources de combustion d’énergie fossiles ou non-fossiles si celles-ci ne sont pas prises en compte dans le module principal.',
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
    en: 'Laboratories',
    fr: 'Laboratoires',
  },
  [`${MODULES.Buildings}.room_type.Archives`]: {
    en: 'Archives',
    fr: 'Archives',
  },
  [`${MODULES.Buildings}.room_type.Libraries`]: {
    en: 'Libraries',
    fr: 'Bibliothèques',
  },
  [`${MODULES.Buildings}.room_type.Auditoriums`]: {
    en: 'Auditoriums',
    fr: 'Auditoires',
  },
  [`${MODULES.Buildings}.inputs.room_surface_square_meter`]: {
    en: 'Surface (m²)',
    fr: 'Surface (m²)',
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

  // Rooms tooltips
  [`${MODULES.Buildings}.tooltips.heating`]: {
    en: 'Annual heating energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie de chauffage calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },
  [`${MODULES.Buildings}.tooltips.cooling`]: {
    en: 'Annual cooling energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie de refroidissement calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },
  [`${MODULES.Buildings}.tooltips.ventilation`]: {
    en: 'Annual ventilation energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie de ventilation calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },
  [`${MODULES.Buildings}.tooltips.lighting`]: {
    en: 'Annual lighting energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie d'éclairage calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },

  // Energy combustion submodule
  [`${MODULES.Buildings}.combustion_table_title`]: {
    en: 'Energy combustion ({count}) | Energy combustions ({count})',
    fr: "Combustion d'énergie ({count}) | Combustions d'énergie ({count})",
  },
  [`${MODULES.Buildings}.add_combustion_button`]: {
    en: 'Add an energy source',
    fr: "Ajouter une source d'énergie",
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
} as const;
