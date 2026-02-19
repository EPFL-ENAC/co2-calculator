import { MODULES } from 'src/constant/modules';

export default {
  [MODULES.Processes]: {
    en: 'Process Emissions',
    fr: 'Emissions de procédés',
  },
  [`${MODULES.Processes}-description`]: {
    en: 'Enter the sources of process gas emissions used in or resulting from chemical or physical reactions in the laboratory.',
    fr: 'Entrez les sources d’émissions de procédé de gaz utilisés dans ou issues de réactions chimiques ou physiques dans le laboratoire.',
  },
  [`${MODULES.Processes}-title-subtext`]: {
    en: 'This module allows to estimate the carbon footprint of greenhouse gases generated during your lab processes (e.g. CO₂ emissions in some SV lab activities, SF₆ emissions when it is used as refrigerant). Emissions generated in the research facilities that you use are excluded, as they are already accounted in the research facilities footprint.',
    fr: 'Ce module permet d’estimer l’empreinte carbone des gaz à effet de serre générés lors de vos activités de laboratoire (par ex. émissions de CO₂ dans certaines activités de laboratoire SV, émissions de SF₆ quand celui-ci est utilisé en tant que fluide frigorigène). Les émissions générées dans les infrastructures de recherche que vous utilisez sont exclues, car elles sont déjà prises en compte dans l’empreinte carbone des infrastructures de recherche.',
  },
  [`${MODULES.Processes}-title-tooltip-title`]: {
    en: 'The amount of each greenhouse gas emitted should be estimated before entering the value in the calculator (e.g. taking into account that only X% of the SF₆ used is ultimately emitted)',
    fr: 'La quantité de chaque gaz à effet de serre émise doit être estimée avant de saisir la valeur dans le calculateur (par ex. en prenant en compte que seulement X % du SF₆ utilisé est finalement émis)',
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
