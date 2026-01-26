import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.EquipmentElectricConsumption]: {
    en: 'Equipment',
    fr: 'Équipements',
  },
  [MODULES_DESCRIPTIONS.EquipmentElectricConsumption]: {
    en: 'Estimate the electrical consumption of all equipment in your unit',
    fr: 'Estimez la consommation électrique de tous les équipements dans votre unité',
  },
  [`${MODULES.EquipmentElectricConsumption}-title-tooltip-title`]: {
    en: 'About Equipment Electric Consumption',
    fr: 'À propos de la consommation électrique des équipements',
  },
  [`${MODULES.EquipmentElectricConsumption}-title-subtext`]: {
    en: `This module allows you to estimate the electrical consumption of the scientific, IT, and other equipment in your unit. The equipment list comes from the equipment inventory carried out by your unit for the faculty. Please fill in the following columns:
Active use and standby use: Please enter the number of hours each piece of equipment is used per week. It is recommended to make a conservative estimate (not underestimated) to minimize the time required for this task. If your equipement active or standby use is different from the one used by default, please contact anna.kouninamasse@epfl.ch.
Subclass: Choose the subclass for equipment where this information is necessary.
Class: Please update the class if the one from your inventory is not appropriate. Note that you will need to apply this change during your next inventory update, as it is not automatically synced through the CO₂ Calculator.`,
    fr: `Ce module permet d'estimer la consommation électrique des équipements scientifiques, IT et autres dans votre unité. La liste de équipements vient de l'inventaire d'équipement effectué par votre unité pour la faculté. Veuillez remplir les colonnes suivantes:
Usage actif et usage standby: veuillez remplir les heures d'utilisation de chaque équipement par semaine. Il est recommandé de faire une estimation conservatrice (qui n'est pas sous-estimée) pour limiter le temps dédié à cette tâche. Si la puissance moyenne active ou standby de votre équipement est différente de celle utilisée par défaut, merci de contacter anna.kouninamasse@epfl.ch.
Sous-classe: choisissez la sous-classe pour les équipements où cette information est nécessaire.
Classe: veuillez mettre à jour la classe si celle de votre inventaire n'est pas appropriée. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour de l'inventaire, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.`,
  },
  [`${MODULES.EquipmentElectricConsumption}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.name`]: {
    en: 'Name',
    fr: 'Nom',
  },
  [`${MODULES.EquipmentElectricConsumption}-scientific`]: {
    en: 'Scientific Equipment',
    fr: 'Équipement scientifique',
  },
  [`${MODULES.EquipmentElectricConsumption}-it`]: {
    en: 'IT Equipment',
    fr: 'Équipement informatique',
  },
  [`${MODULES.EquipmentElectricConsumption}-other`]: {
    en: 'Other Equipment',
    fr: 'Autre équipement',
  },
  [`${MODULES.EquipmentElectricConsumption}-scientific-equipment-table-title`]:
    {
      en: 'Scientific Equipment ({count}) | Scientific Equipments ({count})',
      fr: 'Équipement scientifique ({count}) | Équipements scientifiques ({count})',
    },
  [`${MODULES.EquipmentElectricConsumption}-it-equipment-table-title`]: {
    en: 'IT Equipment ({count}) | IT Equipments ({count})',
    fr: 'Équipement informatique ({count}) | Équipements informatiques ({count})',
  },
  [`${MODULES.EquipmentElectricConsumption}-other-equipment-table-title`]: {
    en: 'Other Equipment ({count}) | Other Equipments ({count})',
    fr: 'Autre équipement ({count}) | Autres équipements ({count})',
  },
  [`${MODULES.EquipmentElectricConsumption}-scientific-form-title`]: {
    en: 'Add Scientific Equipment',
    fr: 'Ajouter un équipement scientifique',
  },
  [`${MODULES.EquipmentElectricConsumption}-it-form-title`]: {
    en: 'Add IT Equipment',
    fr: 'Ajouter un équipement informatique',
  },
  [`${MODULES.EquipmentElectricConsumption}-other-form-title`]: {
    en: 'Add Other Equipment',
    fr: 'Ajouter un autre équipement',
  },
  [`${MODULES.EquipmentElectricConsumption}-scientific-form-title-info-label`]:
    {
      en: 'Remember to update your inventory: if you add an item manually this year, it will not be carried over next year unless you have included it in your inventory.',
      fr: 'Pensez à mettre à jour votre inventaire : si vous ajoutez un élément manuellement cette année, il ne sera pas repris l’année prochaine, sauf si vous l’avez intégré dans votre inventaire.',
    },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.power`]: {
    en: 'The average power is indicated by class. It may not fully represent the power of your equipment, in which case please contact us. Please note that we do not want the maximum power value, which can be very different from the average power.',
    fr: "La puissance moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas merci de nous contacter. Attention, nous ne voulons pas avoir la valeur de puissance maximale qui peut être très différente de la puissance moyenne.",
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.emission`]: {
    en: 'The uncertainty of these values may be high and depends on the representativeness of the power, the hours of use, and the use parameters.',
    fr: "L'incertitude de ces valeurs peut être haute et dépend de la représentativité de la puissance, des heures d'utilisation et des paramètre d'utilisation.",
  },
  equipment_edit_disclaimer: {
    en: `Remember to update your inventory: if you add an item manually this year, it will not be carried over next year unless you have included it in your inventory.`,
    fr: `Pensez à mettre à jour votre inventaire : si vous ajoutez un élément manuellement cette année, il ne sera pas repris l’année prochaine, sauf si vous l’avez intégré dans votre inventaire.`,
  },
  [`${MODULES.EquipmentElectricConsumption}-results-total-electricity-use`]: {
    en: 'Total Electricity Use',
    fr: 'Consommation électrique totale',
  },
  [`${MODULES.EquipmentElectricConsumption}-results-total-electricity-use-tooltip`]:
    {
      en: 'Total electricity consumption of all equipment in the unit',
      fr: "Consommation électrique totale de tous les équipements de l'unité",
    },
  [`${MODULES.EquipmentElectricConsumption}-results-total-electricity-use-comparison`]:
    {
      en: 'Equivalent to the public lighting network of a town of {residents} residents for a full year.',
      fr: "Équivalent au réseau d'éclairage public d'une ville de {residents} habitants pendant une année complète.",
    },
  [`${MODULES.EquipmentElectricConsumption}-results-share-of-lab-total`]: {
    en: "Share of the Lab's total",
    fr: 'Part du total du laboratoire',
  },
  [`${MODULES.EquipmentElectricConsumption}-results-share-of-lab-total-unit`]: {
    en: "of lab's total",
    fr: 'total du lab',
  },
  [`${MODULES.EquipmentElectricConsumption}-results-share-of-lab-total-tooltip`]:
    {
      en: "Percentage of the lab's total carbon footprint represented by equipment electricity consumption",
      fr: "Pourcentage de l'empreinte carbone totale du laboratoire représenté par la consommation électrique des équipements",
    },
  [`${MODULES.EquipmentElectricConsumption}-results-share-of-lab-total-comparison`]:
    {
      en: 'at EPFL in average Electrical Consumption represents {percentage}.',
      fr: "à l'EPFL en moyenne, la consommation électrique représente {percentage}.",
    },
  [`${MODULES.EquipmentElectricConsumption}-results-year-to-year-evolution`]: {
    en: 'Year-to-year Evolution',
    fr: "Évolution d'année en année",
  },
  [`${MODULES.EquipmentElectricConsumption}-results-year-to-year-evolution-tooltip`]:
    {
      en: 'Change in electricity consumption compared to the previous year',
      fr: "Évolution de la consommation électrique par rapport à l'année précédente",
    },
  [`${MODULES.EquipmentElectricConsumption}-results-year-to-year-evolution-comparison`]:
    {
      en: 'Equivalent to {freezers} freezers a full year.',
      fr: 'Équivalent à {freezers} congélateurs pendant une année complète.',
    },
} as const;
