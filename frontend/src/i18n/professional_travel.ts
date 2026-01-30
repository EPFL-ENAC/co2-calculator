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
    en: 'Please enter the details of your trip by train of flight in Switzerland or abroad. Every leg of the journey needs to be entered a new trip (e.g. Lausanne to New York would be 1. a train from Lausanne to Geneva Airport, then 2. a flight from Geneva Airport to Paris-Charles de Gaulle and 3. A flight from Paris-Charles de Gaulle to John F. Kennedy International Airport). The return can be selected by checking the box provided for this purpose.',
    fr: 'Veuillez saisir les détails de votre voyage en train ou en avion, en Suisse ou à l’étranger. Chaque étape du trajet doit être saisie comme un nouveau voyage (par ex. : Lausanne–New York correspondrait à 1. un trajet en train de Lausanne à l’aéroport de Genève, puis 2. un vol de l’aéroport de Genève à Paris–Charles-de-Gaulle et 3. un vol de Paris–Charles-de-Gaulle à l’aéroport international John-F.-Kennedy). Le retour peut être sélectionné en cochant la case prévue à cet effet.',
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
    en: "This module allows you to estimate and visualize the impact of your (or your unit's) travel by train and plane.",
    fr: "Ce module permet d'estimer et de visualiser l'impact de vos voyages (ou de votre unité) en train et en avion.",
  },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint`]: {
    en: 'Total Travel Carbon Footprint',
    fr: 'Empreinte CO₂ totale déplacements',
  },
  [`${MODULES.ProfessionalTravel}-title-tooltip-title`]: {
    en: 'Data relating to your air travel is provided to us by the EPFL Travel Agency, and the associated carbon footprint is calculated taking into account several factors such as distance, class booked, flight altitude, number of people on the plane, airline, etc. If you have traveled outside of the agency, please enter the departure city and arrival city in the tab below. The calculation methodology will then be different and will take into account the distance and type of flight (very short-haul, short-haul, medium-haul, or long-haul).',
    fr: 'Les données relatives à vos voyages en avion nous sont communiquées par l’Agence de voyages EPFL et l’empreinte carbone associée est calculée en considérant plusieurs facteurs tels que la distance, la classe réservée, la hauteur de vol, le nombre de personne dans l’avion, la compagnie aérienne, etc. Si vous avez effectué un voyage hors agence, merci de saisir dans l’onglet ci-dessous, la ville de départ et la ville d’arrivée. La méthodologie de calcul sera alors différente et considérera la distance et le type de vol (très court-courrier, court-courrier, moyen-courrier ou long-courrier).',
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
    en: 'Flight',
    fr: 'Vol',
  },
  [`${MODULES.ProfessionalTravel}-error-same-destination`]: {
    en: 'Origin and destination cannot be the same',
    fr: "L'origine et la destination ne peuvent pas être identiques",
  },
} as const;
