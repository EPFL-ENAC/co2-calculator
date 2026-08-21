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
    en: `Enter your unit's process and fugitive emissions.`,
    fr: 'Saisissez les émissions de procédé et fugitives dans votre unité.',
  },
  [`${MODULES.ProcessEmissions}-title-subtext`]: {
    en: 'This module helps you estimate greenhouse gas emissions from experimental procedures and equipment leaks, such as CO₂ used in lab protocols, SF₆ leaks during etching, fluorinated gas leaks from refrigeration systems, or fluorinated ether evaporation during sample handling.',
    fr: `Ce module vous aide à estimer les émissions de gaz à effet de serre liées à vos procédures expérimentales et aux fuites d’équipements, par exemple : l'utilisation de CO₂ dans les protocoles de laboratoire, les fuites de SF₆ lors de la gravure, les fuites de gaz fluorés des systèmes de réfrigération, ou l’évaporation d’éthers fluorés pendant la manipulation des échantillons. `,
  },
  [`${MODULES.ProcessEmissions}-documentation-link`]: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/processes/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/fr/processes/',
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
  [`${MODULES.ProcessEmissions}.category.Refrigerant`]: {
    en: 'Refrigerant',
    fr: 'Fluide Frigorigène',
  },
  // Factor taxonomy / CSV use singular "refrigerant"; same label as plural key above.
  [`${MODULES.ProcessEmissions}.category.refrigerant`]: {
    en: 'Refrigerant',
    fr: 'Fluide frigorigène',
  },
  // #2091: each fluorinated-gas family is its own leaf; they used to
  // share process_emissions__refrigerants.
  [`${MODULES.ProcessEmissions}.category.sf6`]: {
    en: 'SF₆',
    fr: 'SF₆',
  },
  [`${MODULES.ProcessEmissions}.category.nf3`]: {
    en: 'NF₃',
    fr: 'NF₃',
  },
  [`${MODULES.ProcessEmissions}.category.hfcs`]: {
    en: 'HFCs',
    fr: 'HFC',
  },
  [`${MODULES.ProcessEmissions}.category.perfluorinated_compounds`]: {
    en: 'Perfluorinated compounds',
    fr: 'Composés perfluorés',
  },
  [`${MODULES.ProcessEmissions}.category.fluorinated_ethers`]: {
    en: 'Fluorinated ethers',
    fr: 'Éthers fluorés',
  },
  [`${MODULES.ProcessEmissions}.category.perfluoropolyethers`]: {
    en: 'Perfluoropolyethers',
    fr: 'Perfluoropolyéthers',
  },
  [`${MODULES.ProcessEmissions}.inputs.subcategory`]: {
    en: 'Sub-category',
    fr: 'Sous-catégorie',
  },
  [`${MODULES.ProcessEmissions}.inputs.quantity_kg`]: {
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
