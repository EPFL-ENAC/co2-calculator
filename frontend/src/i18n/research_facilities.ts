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
    en: "Review the use of your unit's research facilities at EPFL.",
    fr: "Examinez l'utilisation des infrastructures de recherche EPFL de votre unité.",
  },
  [`${MODULES.ResearchFacilities}-title-subtext`]: {
    en: "EPFL provides many research facilities such as cleanrooms, high‑performance computing centers, IT infrastructures and services as well as animal facilities, to name just a few. In total, there are more than 40 research facilities and several research centers that are used by the EPFL community, (as well as by other academic institutions, start-ups, companies, and industries). This sharing of resources is an excellent way to reduce carbon footprint.",
    fr: "L'EPFL mutualise de nombreux services internes tels que des salles blanches, des centres de calculs de hautes performances, des services informatiques ou des animaleries, pour n'en nommer que quelques-uns. Au total, il y a plus de 40 plateformes et centres de recherches qui sont utilisés par la communauté EPFL (mais également d'autres institutions académiques ainsi que des start-ups, entreprises et industries). Cette mutualisation des ressources est un excellent moyen de réduire l'empreinte carbone.",
  },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities}-table-title`]:
    {
      en: 'Research facilities ({count})',
      fr: 'Infrastructures de recherche ({count})',
    },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}`]:
    {
      en: 'Mice and fish animal facilities',
      fr: 'Animaleries rongeurs et poissons',
    },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}-table-title`]:
    {
      en: 'Mice and fish animal facilities ({count})',
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
  fish: {
    en: 'Fish',
    fr: 'Poissons',
  },
  mice: {
    en: 'Mice',
    fr: 'Rongeurs',
  },
  [`${MODULES.ResearchFacilities}-title-tooltip-subtext`]: {
    en: 'The methodology used to calculate the carbon footprint of research facilities is documented in the Documentation pages',
    fr: "La méthodologie utilisée pour calculer de l'empreinte carbone des infrastructures de recherche est documentée dans les pages Documentation",
  },
} as const;
