import {
  MODULES,
  SUBMODULE_RESEARCH_FACILITIES_TYPES,
} from 'src/constant/modules';

export default {
  [MODULES.ResearchFacilities]: {
    en: 'EPFL research facilities',
    fr: 'Infrastructures de recherche EPFL',
  },
  [`${MODULES.ResearchFacilities}-description`]: {
    en: "Review your unit's EPFL research facility usage.",
    fr: "Vérifiez les données d'utilisation des infrastructures de recherche EPFL de votre unité.",
  },
  [`${MODULES.ResearchFacilities}-documentation-link`]: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/services/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/fr/services/',
  },
  [`${MODULES.ResearchFacilities}-title-subtext`]: {
    en: `This module helps you estimate the carbon footprint from your unit's use of EPFL internal research facilities.
The carbon footprint allocated to units for each research facility is calculated based on its process emissions, energy combustion, building usage, equipment, and purchases. Depending on the facility, this allocation is based either on funding ratio (billed costs), usage time ratio, or on the number of housing.
Note that if these activities were conducted using your unit’s own standalone resources, their carbon footprint would be significantly higher. Shared use of research facilities helps reduce this overall impact.`,
    fr: `Ce module vous aide à estimer l'empreinte carbone liée à l'utilisation des infrastructures de recherche internes EPFL par votre unité.
L'empreinte carbone de chaque infrastructure de recherche attribuée aux unités est calculée sur la base de ses émissions de procédés, de sa combustion d'énergie, de ses bâtiments, de ses équipements et de ses achats. Selon l'infrastructure, cette répartition s'effectue soit sur la base du ratio de financement (facturation), soit du ratio du temps d'utilisation ou le nombre d'hébergement.
Notez que si ces activités étaient menées avec des moyens propres à l'unité, leur empreinte carbone serait nettement plus élevée. L'utilisation mutualisée d'infrastructures de recherche permet de réduire cet impact global.`,
  },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities}-table-title`]:
    {
      en: 'Research facilities ({count})',
      fr: 'Infrastructures de recherche ({count})',
    },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}`]:
    {
      en: 'Rodent and fish animal facilities',
      fr: 'Animaleries rongeurs et poissons',
    },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}-table-title`]:
    {
      en: 'Rodent and fish animal facilities ({count})',
      fr: 'Animaleries rongeurs et poissons ({count})',
    },
  [`${MODULES.ResearchFacilities}.inputs.name`]: {
    en: 'Research facility',
    fr: 'Infrastructure de recherche',
  },
  [`${MODULES.ResearchFacilities}.inputs.use_unit`]: {
    en: 'Unit',
    fr: 'Unité',
  },
  [`${MODULES.ResearchFacilities}.inputs.use`]: {
    en: 'Use',
    fr: 'Utilisation',
  },
  [`${MODULES.ResearchFacilities}.inputs.type`]: {
    en: 'Type',
    fr: 'Type',
  },
  [`${MODULES.ResearchFacilities}.inputs.nb_housing`]: {
    en: 'Number of housing',
    fr: "Nombre d'hébergements",
  },
  [`${MODULES.ResearchFacilities}.inputs.housing_nb-tooltip`]: {
    en: "For EPFL's rodent and fish animal facilities, only the animal housing component is considered. The Phenotyping Unit (UDP) and the Transgenesis Platform (TCF) are not included.",
    fr: "Pour l'utilisation des animaleries rongeurs et poissons à l'EPFL, nous ne considérons que la partie hébergement des animaux et pas ce qui concerne l'unité de phénotypage (UDP) et la plateforme de transgénèse (TCF).",
  },
  [`${MODULES.ResearchFacilities}.type.fish`]: {
    en: 'Fish',
    fr: 'Poissons',
  },
  [`${MODULES.ResearchFacilities}.type.rodent`]: {
    en: 'Rodents',
    fr: 'Rongeurs',
  },
  [`${MODULES.ResearchFacilities}-title-tooltip-subtext`]: {
    en: 'The methodology used to calculate the carbon footprint of research facilities is documented in the Documentation pages',
    fr: "La méthodologie utilisée pour calculer de l'empreinte carbone des infrastructures de recherche est documentée dans les pages Documentation",
  },
} as const;
