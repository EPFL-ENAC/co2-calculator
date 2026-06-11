import { MODULES, SUBMODULE_EQUIPMENT_TYPES } from 'src/constant/modules';

export default {
  [MODULES.EquipmentElectricConsumption]: {
    en: 'Equipment',
    fr: 'Équipements',
  },
  [`${MODULES.EquipmentElectricConsumption}-title-tooltip-subtext`]: {
    en: 'The emissions from the equipment module contribute to Scope 2 of the laboratory’s carbon footprint.',
    fr: "Les émissions du module équipement contribue au Scope 2 de l'empreinte carbone du laboratoire.",
  },
  [`${MODULES.EquipmentElectricConsumption}-common`]: {
    en: 'Common data and factors | Common data and factors',
    fr: 'Données et facteurs communs | Données et facteurs communs',
  },
  [`${MODULES.EquipmentElectricConsumption}-description`]: {
    en: 'Estimate the electrical consumption of all equipment in your unit',
    fr: 'Estimez la consommation électrique de tous les équipements dans votre unité',
  },

  [`${MODULES.EquipmentElectricConsumption}-title-subtext`]: {
    en: `This module allows you to estimate the electrical consumption of the scientific, IT, and other equipment in your unit. The equipment list comes from the equipment inventory carried out by your unit for the faculty.

Please fill in the following columns:

- Class: Please update the class if the one from your inventory is not appropriate. Note that you will need to apply this change during your next inventory update, as it is not automatically synced through the CO₂ Calculator.

- Subclass: Choose the subclass for equipment where this information is necessary.

- Active use and standby use: Please enter the number of hours each piece of equipment is used per week. It is recommended to make a conservative estimate (not underestimated) to minimize the time required for this task.

If your equipement active or standby power is different from the one used by default, please contact the administrator.`,
    fr: `Ce module permet d'estimer la consommation électrique des équipements scientifiques, IT et autres dans votre unité. La liste de équipements vient de l'inventaire d'équipement effectué par votre unité pour la faculté.

Veuillez remplir les colonnes suivantes:

- Classe: veuillez mettre à jour la classe si celle de votre inventaire n'est pas appropriée. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour de l'inventaire, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.

- Sous-classe: choisissez la sous-classe pour les équipements où cette information est nécessaire.

- Usage actif et usage standby: veuillez mettre à jour les heures d'utilisation de chaque équipement par semaine. Il est recommandé de faire une estimation conservatrice (qui n'est pas sous-estimée) pour limiter le temps dédié à cette tâche.

Si la puissance moyenne active ou standby de votre équipement est différente de celle utilisée par défaut, merci de contacter l'administrateur.`,
  },
  [`${MODULES.EquipmentElectricConsumption}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.name`]: {
    en: 'Name',
    fr: 'Nom',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.equipment_id`]: {
    en: 'Equipment ID (yellow tag)',
    fr: "ID d'équipement (étiquette jaune)",
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.name-placeholder-scientific`]:
    {
      en: 'e.g., Agitator, Centrifuge',
      fr: 'ex. : Agitateur, Centrifugeuse',
    },
  [`${MODULES.EquipmentElectricConsumption}.inputs.name-placeholder-it`]: {
    en: 'e.g., Laptop, Monitor',
    fr: 'ex. : Ordinateur portable, Moniteur',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.name-placeholder-other`]: {
    en: 'e.g., Freezer, Fridge',
    fr: 'ex. : Congélateur, Réfrigérateur',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.class`]: {
    en: 'Class',
    fr: 'Classe',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.subclass`]: {
    en: 'Sub-class',
    fr: 'Sous-classe',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.active_usage`]: {
    en: 'Active usage (h/week)',
    fr: 'Usage actif (h/semaine)',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.standby_usage`]: {
    en: 'Standby usage (h/week)',
    fr: 'Usage standby (h/semaine)',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.active_power`]: {
    en: 'Active power (W)',
    fr: 'Puissance active (W)',
  },
  [`${MODULES.EquipmentElectricConsumption}.inputs.standby_power`]: {
    en: 'Standby power (W)',
    fr: 'Puissance standby (W)',
  },
  [`${MODULES.EquipmentElectricConsumption}-scientific`]: {
    en: 'Scientific Equipment',
    fr: 'Équipements scientifiques',
  },
  [`${MODULES.EquipmentElectricConsumption}-it`]: {
    en: 'IT equipment',
    fr: 'Équipements IT',
  },
  [`${MODULES.EquipmentElectricConsumption}-other`]: {
    en: 'Other equipment',
    fr: 'Autres équipements',
  },
  [`${MODULES.EquipmentElectricConsumption}-scientific-equipment-table-title`]:
    {
      en: 'Scientific Equipment ({count}) | Scientific Equipments ({count})',
      fr: 'Équipement scientifique ({count}) | Équipements scientifiques ({count})',
    },
  [`${MODULES.EquipmentElectricConsumption}-it-equipment-table-title`]: {
    en: 'IT equipment ({count}) | IT equipments ({count})',
    fr: 'Équipements IT ({count}) | Équipements IT ({count})',
  },
  [`${MODULES.EquipmentElectricConsumption}-other-equipment-table-title`]: {
    en: 'Other equipment ({count}) | Other equipments ({count})',
    fr: 'Autres équipements ({count}) | Autres équipements ({count})',
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
  [`${MODULES.EquipmentElectricConsumption}-scientific-form-title-info-tooltip`]:
    {
      en: 'Add a scientific equipment item that is not already in your inventory. Remember to also add it to your official inventory so it is included in future years.',
      fr: 'Ajoutez un équipement scientifique qui ne figure pas encore dans votre inventaire. Pensez également à l’ajouter à votre inventaire officiel afin qu’il soit inclus dans les années futures.',
    },
  [`${MODULES.EquipmentElectricConsumption}-it-form-title-info-tooltip`]: {
    en: 'Add an IT equipment item that is not already in your inventory. Remember to also add it to your official inventory so it is included in future years.',
    fr: 'Ajoutez un équipement informatique qui ne figure pas encore dans votre inventaire. Pensez également à l’ajouter à votre inventaire officiel afin qu’il soit inclus dans les années futures.',
  },
  [`${MODULES.EquipmentElectricConsumption}-other-form-title-info-tooltip`]: {
    en: 'Add another equipment item that is not already in your inventory. Remember to also add it to your official inventory so it is included in future years.',
    fr: 'Ajoutez un autre équipement qui ne figure pas encore dans votre inventaire. Pensez également à l’ajouter à votre inventaire officiel afin qu’il soit inclus dans les années futures.',
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.power`]: {
    en: 'The average power is indicated by class. It may not fully represent the power of your equipment, in which case please contact us. Please note that we do not want the maximum power value, which can be very different from the average power.',
    fr: "La puissance moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas merci de nous contacter. Attention, nous ne voulons pas avoir la valeur de puissance maximale qui peut être très différente de la puissance moyenne.",
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.emission`]: {
    en: 'The uncertainty of these values may be high and depends on the representativeness of the power, the hours of use, and the use parameters.',
    fr: "L'incertitude de ces valeurs peut être haute et dépend de la représentativité de la puissance, des heures d'utilisation et des paramètre d'utilisation.",
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.class`]: {
    en: 'The equipment class determines the average power values used for the emission calculation. Update the class if the one from your inventory is not appropriate.',
    fr: "La classe de l'équipement détermine les valeurs de puissance moyenne utilisées pour le calcul des émissions. Mettez à jour la classe si celle issue de votre inventaire n'est pas appropriée.",
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.subclass`]: {
    en: 'The sub-class allows a more precise determination of the average power values for some equipment classes.',
    fr: "La sous-classe permet une détermination plus précise des valeurs de puissance moyenne pour certaines classes d'équipements.",
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.active_usage`]: {
    en: 'Number of hours per week the equipment is actively in use. It is recommended to make a conservative (not underestimated) estimate.',
    fr: "Nombre d'heures par semaine pendant lesquelles l'équipement est activement utilisé. Il est recommandé de faire une estimation conservatrice (non sous-estimée).",
  },
  [`${MODULES.EquipmentElectricConsumption}.tooltips.standby_usage`]: {
    en: 'Number of hours per week the equipment is on standby (powered on but not actively used). Active and standby hours combined cannot exceed 168 h/wk.',
    fr: "Nombre d'heures par semaine pendant lesquelles l'équipement est en veille (allumé mais non activement utilisé). Les heures actives et standby combinées ne peuvent pas dépasser 168 h/semaine.",
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
  [`${MODULES.EquipmentElectricConsumption}-${SUBMODULE_EQUIPMENT_TYPES.Scientific}-table-title-info-tooltip`]:
    {
      en: 'Check that the data for your scientific equipment are accurate, especially by updating the active and standby use of each piece of equipment.',
      fr: "Vérifiez que les données de vos équipements scientifiques sont correctes, en particulier en mettant à jour l'utilisation active et standby de chaque équipement.",
    },
  [`${MODULES.EquipmentElectricConsumption}-${SUBMODULE_EQUIPMENT_TYPES.IT}-table-title-info-tooltip`]:
    {
      en: 'Check that the data for your IT equipment are accurate, especially by updating the active and standby use of each piece of equipment.',
      fr: "Vérifiez que les données de vos équipements scientifiques sont correctes, en particulier en mettant à jour l'utilisation active et standby de chaque équipement.",
    },
  [`${MODULES.EquipmentElectricConsumption}-${SUBMODULE_EQUIPMENT_TYPES.Other}-table-title-info-tooltip`]:
    {
      en: 'Check that the data for your other equipment are accurate, especially by updating the active and standby use of each piece of equipment.',
      fr: "Vérifiez que les données de vos autres équipements  sont correctes, en particulier en mettant à jour l'utilisation active et standby de chaque équipement.",
    },
} as const;
