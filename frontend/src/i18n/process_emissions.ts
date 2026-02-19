import { MODULES } from 'src/constant/modules';

export default {
  [MODULES.Processes]: {
    en: 'Process Emissions',
    fr: 'Emissions de procédés',
  },
  [`${MODULES.Processes}-description`]: {
    en: 'Enter the sources of process gas emissions from chemical or physical reactions in the laboratory.',
    fr: "Entrez les sources d'émissions de procédé issues des réactions chimiques ou physiques dans le laboratoire.",
  },
  [`${MODULES.Processes}-title-subtext`]: {
    en: 'This module allows to estimate the greenhouse gas emissions (CO₂, CH₄, N₂O, refrigerants) resulting from processes in the laboratory. Data entry is manual.',
    fr: "Ce module permet d'estimer les émissions de gaz à effet de serre (CO₂, CH₄, N₂O, réfrigérants) résultant des procédés de laboratoire. La saisie des données est manuelle.",
  },
  [`${MODULES.Processes}-title-tooltip-title`]: {
    en: 'The amount of each greenhouse gas emitted is converted to CO₂ equivalent using IPCC AR6 GWP values.',
    fr: "La quantité de chaque gaz à effet de serre émis est convertie en équivalent CO₂ à l'aide des valeurs de GWP du GIEC AR6.",
  },
  [`${MODULES.Processes}-process_emission-form-title`]: {
    en: 'Add an emitted gas',
    fr: 'Ajouter un gaz émis',
  },
  [`${MODULES.Processes}-charts-title`]: {
    en: 'Process Emissions Charts',
    fr: 'Graphiques des émissions de procédés',
  },
  [`${MODULES.Processes}-charts-no-data-message`]: {
    en: 'No process emission data available.',
    fr: "Aucune donnée d'émission de procédé disponible.",
  },
  [`${MODULES.Processes}.table_title`]: {
    en: 'Process emission ({count}) | Process emissions ({count})',
    fr: 'Émission de procédé ({count}) | Émissions de procédés ({count})',
  },
  [`${MODULES.Processes}.inputs.emitted_gas`]: {
    en: 'Emitted Gas',
    fr: 'Gaz émis',
  },
  [`${MODULES.Processes}.inputs.sub_category`]: {
    en: 'Sub-category',
    fr: 'Sous-catégorie',
  },
  [`${MODULES.Processes}.inputs.quantity_kg`]: {
    en: 'Quantity (kg)',
    fr: 'Quantité (kg)',
  },
  [`${MODULES.Processes}.add_button`]: {
    en: 'Add an emitted gas',
    fr: 'Ajouter un gaz émis',
  },
  [`${MODULES.Processes}.work_in_progress`]: {
    en: 'work in progress, please validate to confirm your entries',
    fr: "en cours jusqu'à validation de vos entrées",
  },
} as const;
