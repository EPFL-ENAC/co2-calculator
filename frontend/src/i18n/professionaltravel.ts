import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.ProfessionalTravel]: {
    en: 'Professional Travel',
    fr: 'Professional Travel',
  },
  [MODULES_DESCRIPTIONS.ProfessionalTravel]: {
    en: 'Record team travel by plane and train with automatic CO₂ calculations',
    fr: 'Record team trips by plane and train with automatic CO₂ calculations',
  },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint`]: {
    en: 'Total Travel Carbon Footprint',
    fr: 'Empreinte CO₂ totale déplacements',
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
} as const;
