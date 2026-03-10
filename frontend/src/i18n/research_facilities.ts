import { MODULES } from 'src/constant/modules';

export default {
  [MODULES.ResearchFacilities]: {
    en: 'EPFL Research Facilities',
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
    en: '',
    fr: '',
  },
} as const;
