import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.EquipmentElectricConsumption]: {
    en: 'Equipments',
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
  [`${MODULES.EquipmentElectricConsumption}-title-tooltip-description`]: {
    en: `This module allows you to estimate the electrical consumption of the scientific, IT, and other equipment in your unit. The equipment list comes from the equipment inventory carried out by your unit for the faculty. Please fill in the following columns:
Active use and standby use: Please enter the number of hours each piece of equipment is used per week. It is recommended to make a conservative estimate (not underestimated) to minimize the time required for this task. If your equipement active or standby use is different from the one used by default, please contact xxx.
Subclass: Choose the subclass for equipment where this information is necessary.
Class: Please update the class if the one from your inventory is not appropriate. Note that you will need to apply this change during your next inventory update, as it is not automatically synced through the CO₂ Calculator.`,
    fr: `Ce module permet d'estimer la consommation électrique des équipements scientifiques, IT et autres dans votre unité. La liste de équipements vient de l'inventaire d'équipement effectué par votre unité pour la faculté. Veuillez remplir les colonnes suivantes:
Usage actif et usage standby: veuillez remplir les heures d'utilisation de chaque équipement par semaine. Il est recommandé de faire une estimation conservatrice (qui n'est pas sous-estimée) pour limiter le temps dédié à cette tâche. Si la puissance moyenne active ou standby de votre équipement est différente de celle utilisée par défaut, merci de contacter xxx.
Sous-classe: choisissez la sous-classe pour les équipements où cette information est nécessaire.
Classe: veuillez mettre à jour la classe si celle de votre inventaire n'est pas appropriée. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour de l'inventaire, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.`,
  },
  [`${MODULES.EquipmentElectricConsumption}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
} as const;
