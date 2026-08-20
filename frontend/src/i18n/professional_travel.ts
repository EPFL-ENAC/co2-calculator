import { MODULES } from 'src/constant/modules';

export default {
  // Table (Chapter 5)
  [`${MODULES.ProfessionalTravel}-table-title`]: {
    en: 'Professional travel',
    fr: 'Voyages professionnels ',
  },
  [`${MODULES.ProfessionalTravel}-plane-table-title`]: {
    en: 'Plane trip ({count}) | Plane trips ({count})',
    fr: 'Avion ({count}) | Avions ({count})',
  },
  [`${MODULES.ProfessionalTravel}-train-table-title`]: {
    en: 'Train trip ({count}) | Train trips ({count})',
    fr: 'Train ({count}) | Trains ({count})',
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
    en: 'Name',
    fr: 'Nom',
  },
  [`${MODULES.ProfessionalTravel}-field-emissions`]: {
    en: 'kg CO₂-eq',
    fr: 'kg CO₂-eq',
  },
  // Form (Chapter 7)
  [`${MODULES.ProfessionalTravel}-trips-form-title`]: {
    en: 'Add a trip',
    fr: 'Ajoutez un voyage',
  },
  [`${MODULES.ProfessionalTravel}-plane-form-title`]: {
    en: 'Add a plane trip',
    fr: 'Ajoutez un trajet en avion',
  },
  [`${MODULES.ProfessionalTravel}-train-form-title`]: {
    en: 'Add a train trip',
    fr: 'Ajoutez un trajet en train',
  },
  [`${MODULES.ProfessionalTravel}-other-form-title`]: {
    en: 'Add a trip',
    fr: 'Ajoutez un voyage',
  },
  [`${MODULES.ProfessionalTravel}-field-return-date`]: {
    en: 'Return date',
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
  [`${MODULES.ProfessionalTravel}-plane`]: {
    en: 'plane',
    fr: 'avion',
  },
  [`${MODULES.ProfessionalTravel}-train`]: {
    en: 'train',
    fr: 'train',
  },
  [`${MODULES.ProfessionalTravel}-add-plane-button`]: {
    en: 'Add a plane trip',
    fr: 'Ajouter un trajet en avion',
  },
  [`${MODULES.ProfessionalTravel}-add-train-button`]: {
    en: 'Add a train trip',
    fr: 'Ajouter un trajet en train',
  },
  // Legacy keys (keeping for backward compatibility)
  [MODULES.ProfessionalTravel]: {
    en: 'Professional travel',
    fr: 'Voyages professionnels ',
  },
  [`${MODULES.ProfessionalTravel}-description`]: {
    en: "View and enter your unit's professional travel information.",
    fr: 'Consultez et renseignez les voyages professionnels de votre unité.',
  },
  [`${MODULES.ProfessionalTravel}-title-subtext`]: {
    en: "This module allows you to estimate and visualize the impact of your (or your unit's) travel by train and plane. Data relating to your air travel is provided to us by the EPFL Travel Agency, and the associated carbon footprint is calculated taking into account several factors such as distance, class booked, flight altitude, number of people on the plane, airline, etc. If you have traveled outside of the agency, please enter the departure city and arrival city in the tab below. The calculation methodology will then be different and will take into account the distance and type of flight (very short-haul, short-haul, medium-haul, or long-haul).",
    fr: "Ce module permet d'estimer et de visualiser l'impact de vos voyages (ou de votre unité) en train et en avion. Les données relatives à vos voyages en avion nous sont communiquées par l’Agence de voyages EPFL et l’empreinte carbone associée est calculée en considérant plusieurs facteurs tels que la distance, la classe réservée, la hauteur de vol, le nombre de personne dans l’avion, la compagnie aérienne, etc. Si vous avez effectué un voyage hors agence, merci de saisir dans l’onglet ci-dessous, la ville de départ et la ville d’arrivée. La méthodologie de calcul sera alors différente et considérera la distance et le type de vol (très court-courrier, court-courrier, moyen-courrier ou long-courrier).",
  },
  [`${MODULES.ProfessionalTravel}-documentation-link`]: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/professional-travel/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/fr/professional-travel/',
  },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint`]: {
    en: 'Total travel carbon footprint',
    fr: 'Empreinte carbone totale déplacements',
  },
  [`${MODULES.ProfessionalTravel}-results-total-travel-carbon-footprint-comparison`]:
    {
      en: 'is equivalent to ~{km} km driven with car',
      fr: 'équivaut à ~{km} km parcourus en voiture',
    },
  // Class keys
  class_1: {
    en: '1st class',
    fr: '1ère classe',
  },
  class_2: {
    en: '2nd class',
    fr: '2ème classe',
  },
  first: {
    en: '1st class',
    fr: '1ère classe',
  },
  business: {
    en: 'Business',
    fr: 'Business',
  },
  eco: {
    en: 'Eco',
    fr: 'Eco',
  },
  eco_plus: {
    en: 'Eco+',
    fr: 'Eco+',
  },
  // Category keys
  train: {
    en: 'Train',
    fr: 'Train',
  },
  plane: {
    en: 'Plane',
    fr: 'Avion',
  },
  [`${MODULES.ProfessionalTravel}-error-same-destination`]: {
    en: 'Origin and destination cannot be the same',
    fr: "L'origine et la destination ne peuvent pas être identiques",
  },
  [`${MODULES.ProfessionalTravel}-error-location-not-selected`]: {
    en: 'Select a location from the suggestions',
    fr: 'Sélectionnez un lieu dans les suggestions',
  },
  [`${MODULES.ProfessionalTravel}-field-traveler-empty-headcount`]: {
    en: 'No headcount members found. Add members in the Headcount module first.',
    fr: 'Aucun membre du personnel trouvé. Ajoutez des membres dans le module Personnel.',
  },
  [`${MODULES.ProfessionalTravel}-field-traveler-not-validated`]: {
    en: 'You have not been validated in the headcount. Please contact your unit manager.',
    fr: "Vous n'avez pas été validé dans les effectifs. Veuillez contacter votre responsable d'unité.",
  },
  // Sentinel travelers not tied to a headcount member (issue #1153)
  [`${MODULES.ProfessionalTravel}-field-traveler-other-internal`]: {
    en: 'Other traveler (internal)',
    fr: 'Autre (interne)',
  },
  [`${MODULES.ProfessionalTravel}-field-traveler-other-external`]: {
    en: 'Other traveler (external)',
    fr: 'Autre (externe)',
  },

  // Trip-map widget (issue #282). One Pinia slot feeds three maps —
  // the overall map on the carbon-footprint card and the plane/train
  // maps inside their respective submodule cards.
  [`${MODULES.ProfessionalTravel}-trips-map-title-overall`]: {
    en: 'Trips map',
    fr: 'Carte des voyages',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-title-plane`]: {
    en: 'Plane trips map',
    fr: 'Carte des voyages en avion',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-title-train`]: {
    en: 'Train trips map',
    fr: 'Carte des voyages en train',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-empty`]: {
    en: 'No trips with known coordinates to display.',
    fr: 'Aucun voyage avec des coordonnées connues à afficher.',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-aria-label`]: {
    en: 'Map of professional travel trips',
    fr: 'Carte des déplacements professionnels',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-leg-aria`]: {
    en: '{from} to {to}: {count} trips, {emissions}',
    fr: '{from} à {to} : {count} voyages, {emissions}',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-popup-trips`]: {
    en: '{count} trip | {count} trips',
    fr: '{count} voyage | {count} voyages',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-popup-mode`]: {
    en: 'Mode',
    fr: 'Mode',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-popup-avg`]: {
    en: 'Avg / trip',
    fr: 'Moy. / trajet',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-popup-travelers`]: {
    en: 'Traveler | Travelers',
    fr: 'Voyageur·euse | Voyageur·euses',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-legend-emissions`]: {
    en: 'Emissions',
    fr: 'Émissions',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-legend-trips`]: {
    en: 'Trips',
    fr: 'Voyages',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-filter-members-title`]: {
    en: 'Unit members',
    fr: "Membres de l'unité",
  },
  [`${MODULES.ProfessionalTravel}-trips-map-filter-members-label`]: {
    en: '({shown}/{total} shown)',
    fr: '({shown}/{total} affichés)',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-filter-members-aria`]: {
    en: 'Filter trips by unit member',
    fr: "Filtrer les voyages par membre de l'unité",
  },
  [`${MODULES.ProfessionalTravel}-trips-map-filter-all`]: {
    en: 'All',
    fr: 'Tout',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-filter-mode-aria`]: {
    en: 'Filter trips by mode',
    fr: 'Filtrer les voyages par mode',
  },
  [`${MODULES.ProfessionalTravel}-trips-map-filter-none`]: {
    en: 'None',
    fr: 'Aucun',
  },
} as const;
