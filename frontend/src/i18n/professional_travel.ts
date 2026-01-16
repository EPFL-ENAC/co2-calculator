import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  // Table (Chapter 5)
  [`${MODULES.ProfessionalTravel}-table-title`]: {
    en: 'Trips',
    fr: 'Voyages',
  },
  [`${MODULES.ProfessionalTravel}-field-type`]: {
    en: 'Type',
    fr: 'Type',
  },
  [`${MODULES.ProfessionalTravel}-field-from`]: {
    en: 'From',
    fr: 'De',
  },
  [`${MODULES.ProfessionalTravel}-field-to`]: {
    en: 'To',
    fr: 'À',
  },
  [`${MODULES.ProfessionalTravel}-field-start-date`]: {
    en: 'Date',
    fr: 'Date ',
  },
  [`${MODULES.ProfessionalTravel}-field-number-trips`]: {
    en: 'Number of trips',
    fr: 'Nombre de trajets',
  },
  [`${MODULES.ProfessionalTravel}-field-distance`]: {
    en: 'Distance (km)',
    fr: 'Distance (km)',
  },
  [`${MODULES.ProfessionalTravel}-field-traveler`]: {
    en: 'Traveler Name',
    fr: 'Nom du voyageur',
  },
  [`${MODULES.ProfessionalTravel}-field-emissions`]: {
    en: 'kg CO₂-eq',
    fr: 'kg CO₂-eq',
  },
  // Form (Chapter 7)
  [`${MODULES.ProfessionalTravel}-trips-form-title`]: {
    en: 'Add a trip',
    fr: 'Ajouter un voyage',
  },
  [`${MODULES.ProfessionalTravel}-form-tooltip`]: {
    en: 'Each leg of a journey must be entered as a separate trip.',
    fr: 'Chaque étape du trajet doit être saisie comme un déplacement distinct.',
  },
  [`${MODULES.ProfessionalTravel}-other-form-title`]: {
    en: 'Add a trip',
    fr: 'Ajouter un voyage',
  },
  [`${MODULES.ProfessionalTravel}-field-return-date`]: {
    en: 'Return Date',
    fr: 'Date de retour',
  },
  [`${MODULES.ProfessionalTravel}-field-round-trip`]: {
    en: 'Round trip',
    fr: 'Aller-retour',
  },
  [`${MODULES.ProfessionalTravel}-field-class`]: {
    en: 'Class',
    fr: 'Classe',
  },
  [`${MODULES.ProfessionalTravel}-field-purpose`]: {
    en: 'Purpose',
    fr: 'Motif',
  },
  [`${MODULES.ProfessionalTravel}-field-notes`]: {
    en: 'Notes',
    fr: 'Notes',
  },
  // Submodule name (used in form labels)
  [`${MODULES.ProfessionalTravel}-trips`]: {
    en: 'trip',
    fr: 'voyage',
  },
  // Legacy keys (keeping for backward compatibility)
  [MODULES.ProfessionalTravel]: {
    en: 'Professional Travel',
    fr: 'Voyages professionnels ',
  },
  [MODULES_DESCRIPTIONS.ProfessionalTravel]: {
    en: 'Record travel by plane and train, along with their associated emissions. ',
    fr: 'Enregistrez les déplacements en avion et en train, ainsi que les émissions associées.',
  },
  [`${MODULES.ProfessionalTravel}-title-subtext`]: {
    en: 'Please manually complete all train trips. Plane trips are usually already listed in the table below.',
    fr: 'Veuillez renseigner manuellement tous les trajets en train. Les trajets en avion sont généralement déjà renseignés dans le tableau ci-dessous.',
  },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint`]: {
    en: 'Total Travel Carbon Footprint',
    fr: 'Empreinte CO₂ totale déplacements',
  },
  [`${MODULES.ProfessionalTravel}-title-tooltip-title`]: {
    en: 'Information',
    fr: 'Information',
  },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint-tooltip`]:
    {
      en: 'Total carbon footprint from all professional travel including flights, trains, and commuting',
      fr: 'Empreinte carbone totale de tous les déplacements professionnels incluant les vols, trains et trajets domicile-travail',
    },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint-comparison`]:
    {
      en: 'is equivalent to ~{km} km driven with car',
      fr: 'équivaut à ~{km} km parcourus en voiture',
    },
  [`${MODULES.ProfessionalTravel}-results-travel-per-fte`]: {
    en: 'Travel per FTE',
    fr: 'Déplacements par ETP',
  },
  [`${MODULES.ProfessionalTravel}-results-travel-per-fte-unit`]: {
    en: 'per FTE',
    fr: 'par ETP',
  },
  [`${MODULES.ProfessionalTravel}-results-travel-per-fte-tooltip`]: {
    en: 'Average travel carbon footprint per Full-Time Equivalent employee',
    fr: 'Empreinte carbone moyenne des déplacements par équivalent temps plein',
  },
  [`${MODULES.ProfessionalTravel}-results-travel-per-fte-comparison`]: {
    en: 'at EPFL in average Professional Travel represents {percentage}.',
    fr: "à l'EPFL en moyenne, les déplacements professionnels représentent {percentage}.",
  },
  [`${MODULES.ProfessionalTravel}-results-year-to-year-evolution`]: {
    en: 'Year-to-year Evolution',
    fr: "Évolution d'année en année",
  },
  [`${MODULES.ProfessionalTravel}-results-year-to-year-evolution-tooltip`]: {
    en: 'Change in travel carbon footprint compared to the previous year',
    fr: "Évolution de l'empreinte carbone des déplacements par rapport à l'année précédente",
  },
  [`${MODULES.ProfessionalTravel}-results-year-to-year-evolution-comparison`]: {
    en: 'Equivalent to {trips} trips a full year.',
    fr: 'Équivalent à {trips} voyages pendant une année complète.',
  },
  // Class keys
  class_1: {
    en: 'Class 1',
    fr: 'Classe 1',
  },
  class_2: {
    en: 'Class 2',
    fr: 'Classe 2',
  },
  first: {
    en: 'First',
    fr: 'Première',
  },
  business: {
    en: 'Business',
    fr: 'Affaires',
  },
  eco: {
    en: 'Eco',
    fr: 'Éco',
  },
  eco_plus: {
    en: 'Eco+',
    fr: 'Éco+',
  },
  // Category keys
  train: {
    en: 'Train',
    fr: 'Train',
  },
  flight: {
    en: 'Plane',
    fr: 'Avion',
  },
} as const;
