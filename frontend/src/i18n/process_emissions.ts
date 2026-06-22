import { MODULES } from 'src/constant/modules';

export default {
  documentation_editing_rows_process_emissions_topic: {
    en: 'Process emissions',
    fr: 'Émissions de procédés',
  },
  documentation_editing_rows_process_emissions_description: {
    en: 'Find all text related to process emissions within the application.',
    fr: "Trouvez tous les textes liés aux émissions de procédés dans l'application.",
  },
  [MODULES.ProcessEmissions]: {
    en: 'Process emissions',
    fr: 'Emissions de procédés',
  },
  [`${MODULES.ProcessEmissions}-description`]: {
    en: 'Enter the sources of process gas emissions used in or resulting from chemical or physical reactions in the laboratory.',
    fr: 'Entrez les sources d’émissions de procédé de gaz utilisés dans ou issues de réactions chimiques ou physiques dans le laboratoire.',
  },
  [`${MODULES.ProcessEmissions}-title-subtext`]: {
    en: 'This module allows to estimate the carbon footprint of greenhouse gases generated during your lab processes (e.g. CO₂ emissions in some lab activities, SF₆ emissions when it is used as refrigerant). Emissions generated in the research facilities that you use are excluded, as they are already accounted in the relavant module. For more information: For more information: [processes](https://epfl-enac.github.io/co2-calculator-user-doc/processes/)',
    fr: 'Ce module permet d’estimer l’empreinte carbone des gaz à effet de serre générés lors de vos activités de laboratoire (e.g. émissions de CO₂ dans certaines activités de laboratoire, émissions de SF₆ quand celui-ci est utilisé en tant que fluide frigorigène). Les émissions générées dans les infrastructures de recherche que vous utilisez sont exclues, car elles sont déjà prises en compte dans le module relatif. Pour plus d'information : [procédés](https://epfl-enac.github.io/co2-calculator-user-doc/fr/processes/)',
  },
  [`${MODULES.ProcessEmissions}-process_emissions-form-title`]: {
    en: 'Add an emitted gas',
    fr: 'Ajoutez un gaz émis',
  },
  [`${MODULES.ProcessEmissions}-charts-title`]: {
    en: 'Process emission carbon footprint',
    fr: 'Empreinte carbone emissions de procédés',
  },
  [`${MODULES.ProcessEmissions}-charts-no-data-message`]: {
    en: 'No process emission data available.',
    fr: "Aucune donnée d'émission de procédé disponible.",
  },
  [`${MODULES.ProcessEmissions}.table_title`]: {
    en: 'Process emission ({count}) | Process emissions ({count})',
    fr: 'Émission de procédé ({count}) | Émissions de procédés ({count})',
  },
  [`${MODULES.ProcessEmissions}.inputs.category`]: {
    en: 'Emitted gas',
    fr: 'Gaz émis',
  },
  [`${MODULES.ProcessEmissions}.category.co2`]: {
    en: 'CO₂',
    fr: 'CO₂',
  },
  [`${MODULES.ProcessEmissions}.category.ch4`]: {
    en: 'CH₄',
    fr: 'CH₄',
  },
  [`${MODULES.ProcessEmissions}.category.n2o`]: {
    en: 'N₂O',
    fr: 'N₂O',
  },
  [`${MODULES.ProcessEmissions}.category.refrigerants`]: {
    en: 'Refrigerant',
    fr: 'Fluide frigorigène',
  },
  // Factor taxonomy / CSV use singular "refrigerant"; same label as plural key above.
  [`${MODULES.ProcessEmissions}.category.refrigerant`]: {
    en: 'Refrigerant',
    fr: 'Fluide frigorigène',
  },
  [`${MODULES.ProcessEmissions}.inputs.subcategory`]: {
    en: 'Sub-category',
    fr: 'Sous-catégorie',
  },
  [`${MODULES.ProcessEmissions}.inputs.quantity`]: {
    en: 'Quantity (kg)',
    fr: 'Quantité (kg)',
  },
  [`${MODULES.ProcessEmissions}.add_button`]: {
    en: 'Add',
    fr: 'Ajouter',
  },
  [`${MODULES.ProcessEmissions}.work_in_progress`]: {
    en: 'work in progress, please validate to confirm your entries',
    fr: "en cours jusqu'à validation de vos entrées",
  },
} as const;
