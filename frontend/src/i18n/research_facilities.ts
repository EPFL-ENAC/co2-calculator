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
    en: "Review the use of your unit's research facilities (at EPFL).",
    fr: "Examinez l'utilisation des infrastructures de recherche EPFL de votre unité.",
  },
  [`${MODULES.ResearchFacilities}-title-subtext`]: {
    en: "EPFL provides many research facilities such as cleanrooms, high‑performance computing centers, IT infrastructures and services as well as animal facilities, to name just a few. In total, there are more than 40 research facilities and several research centers that are used by the EPFL community, (as well as by other academic institutions, start-ups, companies, and industries). This sharing of resources is an excellent way to reduce carbon footprint. Review your unit's use of EPFL research infrastructure and/or animal facilities.",
    fr: "L'EPFL mutualise de nombreux services internes tels que des salles blanches, des centres de calculs de hautes performances, des services informatiques ou des animaleries, pour n'en nommer que quelques-uns. Au total, il y a plus de 40 plateformes et centres de recherches qui sont utilisés par la communauté EPFL (mais également d'autres institutions académiques ainsi que des start-ups, entreprises et industries). Cette mutualisation des ressources est un excellent moyen de réduire l'empreinte carbone. Examinez l'utilisation des infrastructures de recherche et/ou des animaleries EPFL par votre unité.",
  },
  [`${MODULES.ResearchFacilities}-title-tooltip-title`]: {
    en: 'The methodology used to calculate the carbon footprint of research facilities is documented in the Documentation pages',
    fr: "La méthodologie utilisée pour calculer de l'empreinte carbone des infrastructures de recherche est documentée dans les pages Documentation",
  },
  [`${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities}-table-title`]:
    {
      en: 'Research Facilities ({count})',
      fr: 'Infrastructures de recherche ({count})',
    },
  [`${MODULES.ResearchFacilities}-${SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities}-table-title-info-tooltip`]:
    {
      en: 'Emissions from research facilities allocated to the units are calculated based on Process emission, Energy combustion, Building, Equipment, and Purchases emissions, using billing or the number of hours used by your unit as the allocation key. If one or several research facilities are missing in the tool, do not hesitate to contact us so that we can provide you with more details.',
      fr: "Les émissions des infrastructures de recherche attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Combustion d'énergie, Bâtiments, Équipements et Achats en considérant comme clé de répartition les facturations ou le nombre d'heures d'utilisation de votre unité. Si une ou plusieurs infrastructures de recherche manquent dans l'outil, n'hésitez pas à nous contacter afin que nous puissions vous fournir plus de détails.",
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
  [`${MODULES.ResearchFacilities}-${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}-table-title-info-tooltip`]:
    {
      en: 'The emissions from the mice and fish facilities are allocated to the units and calculated based on Process emission, Energy combustion, Building, Equipment, and Purchases emissions, using the number of housing units (cages, aquariums) per year as the allocation key.',
      fr: "Les émissions des animaleries rongeurs et poissons sont attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Combustion d'énergie, Bâtiments, Équipements et Achats en considérant comme clé de répartition le nombre d'hébergements (cages, aquariums) par année.",
    },
  [`${MODULES.ResearchFacilities}.inputs.name`]: {
    en: 'Research Facility',
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
    en: 'For the mice and fish facilities of the CPG unit, we consider only the annual housing component, and not phenotyping or UDP.',
    fr: "Pour les animaleries rongeurs et poissons de l'unité CPG, nous ne considérons que la partie hébergement annuel et non le phénotypage ou UDP.",
  },
} as const;
