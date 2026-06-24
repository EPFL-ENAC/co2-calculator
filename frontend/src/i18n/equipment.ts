import { MODULES } from 'src/constant/modules';

export default {
  [MODULES.Equipment]: {
    en: 'Equipment',
    fr: 'Équipements',
  },
  [`${MODULES.Equipment}-common`]: {
    en: 'Common data and factors | Common data and factors',
    fr: 'Données et facteurs communs | Données et facteurs communs',
  },
  [`${MODULES.Equipment}-description`]: {
    en: 'Estimate the electrical consumption of your equipment',
    fr: 'Estimez la consommation électrique de vos équipements',
  },

  [`${MODULES.Equipment}-title-subtext`]: {
    en: `This module allows you to estimate the electrical consumption of your scientific, IT, and other equipment. The equipment list comes from the inventory carried out by your unit for the faculty.

Please fill in the following columns:

- Subclass: Choose the subclass for equipment where this information is necessary.

- Active use and standby use: Please enter the number of hours each piece of equipment is used per week. It is recommended to make a conservative estimate (not underestimated) to minimize the time required for this task.

If your equipement active or standby power is different from the one used by default, please contact the administrator.

For more information: [equipment](https://epfl-enac.github.io/co2-calculator-user-doc/equipment/)`,
    fr: `Ce module permet d'estimer la consommation électrique de vos équipements scientifiques, IT et autres. La liste de équipements vient de l'inventaire effectué par votre unité pour la faculté.

Veuillez remplir les colonnes suivantes:

- Sous-classe: choisissez la sous-classe pour les équipements où cette information est nécessaire.

- Usage actif et usage standby: veuillez mettre à jour les heures d'utilisation de chaque équipement par semaine. Il est recommandé de faire une estimation conservatrice (qui n'est pas sous-estimée) pour limiter le temps dédié à cette tâche.

Si la puissance moyenne active ou standby de votre équipement est différente de celle utilisée par défaut, merci de contacter l'administrateur.

Pour plus d'information : [équipments](https://epfl-enac.github.io/co2-calculator-user-doc/fr/equipment/)`,
  },
  [`${MODULES.Equipment}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
  [`${MODULES.Equipment}.inputs.name`]: {
    en: 'Name',
    fr: 'Nom',
  },
  [`${MODULES.Equipment}.inputs.equipment_id`]: {
    en: 'Equipment ID (yellow tag)',
    fr: "ID d'équipement (étiquette jaune)",
  },
  [`${MODULES.Equipment}.inputs.name-placeholder-scientific`]: {
    en: 'e.g., Agitator, Centrifuge',
    fr: 'ex. : Agitateur, Centrifugeuse',
  },
  [`${MODULES.Equipment}.inputs.name-placeholder-scientific`]: {
    en: 'e.g., Agitator, Centrifuge',
    fr: 'ex. : Agitateur, Centrifugeuse',
  },
  [`${MODULES.Equipment}.inputs.name-placeholder-it`]: {
    en: 'e.g., Laptop, Monitor',
    fr: 'ex. : Ordinateur portable, Moniteur',
  },
  [`${MODULES.Equipment}.inputs.name-placeholder-other`]: {
    en: 'e.g., Freezer, Fridge',
    fr: 'ex. : Congélateur, Réfrigérateur',
  },
  [`${MODULES.Equipment}.inputs.class`]: {
    en: 'Class',
    fr: 'Classe',
  },
  [`${MODULES.Equipment}.inputs.subclass`]: {
    en: 'Sub-class',
    fr: 'Sous-classe',
  },
  [`${MODULES.Equipment}.inputs.active_usage`]: {
    en: 'Active usage (h/week)',
    fr: 'Usage actif (h/semaine)',
  },
  [`${MODULES.Equipment}.inputs.standby_usage`]: {
    en: 'Standby usage (h/week)',
    fr: 'Usage standby (h/semaine)',
  },
  [`${MODULES.Equipment}.inputs.active_power`]: {
    en: 'Active power (W)',
    fr: 'Puissance active (W)',
  },
  [`${MODULES.Equipment}.inputs.standby_power`]: {
    en: 'Standby power (W)',
    fr: 'Puissance standby (W)',
  },
  [`${MODULES.Equipment}-scientific`]: {
    en: 'Scientific equipment',
    fr: 'Équipements scientifiques',
  },
  [`${MODULES.Equipment}-it`]: {
    en: 'IT equipment',
    fr: 'Équipements IT',
  },
  [`${MODULES.Equipment}-other`]: {
    en: 'Other equipment',
    fr: 'Autres équipements',
  },
  [`${MODULES.Equipment}-scientific-equipment-table-title`]: {
    en: 'Scientific equipment ({count}) | Scientific equipment ({count})',
    fr: 'Équipement scientifique ({count}) | Équipements scientifiques ({count})',
  },
  [`${MODULES.Equipment}-it-equipment-table-title`]: {
    en: 'IT equipment ({count}) | IT equipments ({count})',
    fr: 'Équipements IT ({count}) | Équipements IT ({count})',
  },
  [`${MODULES.Equipment}-other-equipment-table-title`]: {
    en: 'Other equipment ({count}) | Other equipments ({count})',
    fr: 'Autres équipements ({count}) | Autres équipements ({count})',
  },
  [`${MODULES.Equipment}-scientific-form-title`]: {
    en: 'Add scientific equipment',
    fr: 'Ajouter un équipement scientifique',
  },
  [`${MODULES.Equipment}-it-form-title`]: {
    en: 'Add IT equipment',
    fr: 'Ajouter un équipement informatique',
  },
  [`${MODULES.Equipment}-other-form-title`]: {
    en: 'Add other equipment',
    fr: 'Ajouter un autre équipement',
  },
  [`${MODULES.Equipment}-scientific-form-title-info-label`]: {
    en: 'Remember to update your inventory: if you add an item manually this year, it will not be carried over next year unless you have included it in your inventory.',
    fr: 'Pensez à mettre à jour votre inventaire : si vous ajoutez un élément manuellement cette année, il ne sera pas repris l’année prochaine, sauf si vous l’avez intégré dans votre inventaire.',
  },
  equipment_edit_disclaimer: {
    en: `Remember to update your inventory: if you add an item manually this year, it will not be carried over next year unless you have included it in your inventory.`,
    fr: `Pensez à mettre à jour votre inventaire : si vous ajoutez un élément manuellement cette année, il ne sera pas repris l’année prochaine, sauf si vous l’avez intégré dans votre inventaire.`,
  },
  [`${MODULES.Equipment}-results-total-electricity-use`]: {
    en: 'Total Electricity Use',
    fr: 'Consommation électrique totale',
  },
  [`${MODULES.Equipment}-results-total-electricity-use-comparison`]: {
    en: 'Equivalent to the public lighting network of a town of {residents} residents for a full year.',
    fr: "Équivalent au réseau d'éclairage public d'une ville de {residents} habitants pendant une année complète.",
  },
  [`${MODULES.Equipment}-results-share-of-lab-total`]: {
    en: "Share of the Lab's total",
    fr: 'Part du total du laboratoire',
  },
  [`${MODULES.Equipment}-results-share-of-lab-total-unit`]: {
    en: "of lab's total",
    fr: 'total du lab',
  },
  [`${MODULES.Equipment}-results-share-of-lab-total-comparison`]: {
    en: 'at EPFL in average Electrical consumption represents {percentage}.',
    fr: "à l'EPFL en moyenne, la consommation électrique représente {percentage}.",
  },
  [`${MODULES.Equipment}-results-year-to-year-evolution`]: {
    en: 'Year-to-year evolution',
    fr: "Évolution d'année en année",
  },
  [`${MODULES.Equipment}-results-year-to-year-evolution-comparison`]: {
    en: 'Equivalent to {freezers} freezers a full year.',
    fr: 'Équivalent à {freezers} congélateurs pendant une année complète.',
  },
} as const;
