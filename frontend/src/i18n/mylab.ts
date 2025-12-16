import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.MyLab]: {
    en: 'Headcount',
    fr: 'Personnel',
  },
  [MODULES_DESCRIPTIONS.MyLab]: {
    en: 'Enter and verify team members and Full Time Equivalent (FTE) values for your unit',
    fr: 'Saisissez et vérifiez les membres de l’équipe et leurs équivalents plein-temps (EPT) pour votre unité',
  },
  [`${MODULES.MyLab}-title-subtext`]: {
    en: `This module automatically displays the names, roles, and FTE values of your unit’s personnel as of the end of the year. Review and make any necessary adjustments to ensure your team profile is complete. For student contributions, use the integrated Student FTE Calculator Helper to add their total FTE over the year.`,
    fr: `Ce module affiche automatiquement les noms, rôles et EPT des membres de votre unité à la fin de l’année. Passez en revue ces informations et apportez les ajustements nécessaires pour garantir que le profil de votre équipe soit complet. Pour les contributions des étudiants, utilisez l’outil intégré Calculateur d’EPT étudiants afin d’ajouter leur EPT total sur l’année.`,
  },
  [`${MODULES.MyLab}-title-tooltip-title`]: {
    en: 'The total FTE is used to generate the generic indicators for Food and Commuting, as well as total carbon footprint per FTE for your unit.',
    fr: "Le nombre total d'EPT est utilisé pour générer les indicateurs génériques relatifs à l'Alimentation et au Mobilité pendulaire, ainsi que l'empreinte carbone totale par EPT pour votre unité.",
  },

  [`${MODULES.MyLab}-member-table-title`]: {
    en: 'Member ({count})| Members ({count})',
    fr: 'Membre ({count})| Membres ({count})',
  },
  [`${MODULES.MyLab}-student-table-title`]: {
    en: 'Students',
    fr: 'Étudiants',
  },
  [`${MODULES.MyLab}-member-table-title-info-tooltip`]: {
    en: 'You can add data one at a time using the Add FTE below, or upload several entries at once using a file that follows the template.',
    fr: 'Vous pouvez ajouter les données une par une en utilisant le bouton « Ajouter un EPT » ci-dessous, ou importer plusieurs entrées à la fois via un fichier respectant le modèle fourni.',
  },
  [`${MODULES.MyLab}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
  [`${MODULES.MyLab}-member-form-title`]: {
    // en: 'Add Full-Time Equivalent member',
    // fr: 'Ajouter un membre à équivalent plein-temps',
    en: 'Add FTE',
    fr: 'Ajouter un EPT',
  },
  [`${MODULES.MyLab}-member-form-title`]: {
    // en: 'Add Full-Time Equivalent member',
    // fr: 'Ajouter un membre à équivalent plein-temps',
    en: 'Add FTE',
    fr: 'Ajouter un EPT',
  },
  // module member

  [`${MODULES.MyLab}-member-form-field-fte-label`]: {
    en: 'Full-Time Equivalent (FTE)',
    fr: 'Équivalent plein-temps (EPT)',
  },
  [`${MODULES.MyLab}-member-form-field-position-label`]: {
    en: 'Position',
    fr: 'Position',
  },
  [`${MODULES.MyLab}-member-form-field-name-label`]: {
    en: 'Name',
    fr: 'Nom',
  },
  // module_mylab_student_form_field_fte_label
  [`${MODULES.MyLab}-student_form_field_fte_label`]: {
    en: 'Total Student FTE',
    fr: 'EPT étudiants total',
  },
  [`${MODULES.MyLab}-student-form-title`]: {
    en: 'Student FTE',
    fr: 'EPT étudiants',
  },

  [`${MODULES.MyLab}-student-form-subtitle`]: {
    en: `Please use the
      Student FTE Calculator Helper below, then enter the aggregated usage time.
    `,
    fr: `Veuillez utiliser l'outil Calculateur d’EPT étudiants ci-dessous, puis saisir le temps d'utilisation agrégé.`,
  },
  [`${MODULES.MyLab}-student-student-helper-title`]: {
    en: 'Student FTE Calculator Helper',
    fr: 'FTE étudiants - Outil d’aide au calcul',
  },
  [`${MODULES.MyLab}-member-form-title-info-label`]: {
    en: 'fte member tooltip',
    fr: '',
  },
  [`${MODULES.MyLab}-member-form-title-info-tooltip`]: {
    en: 'lorem ipsum',
    fr: '',
  },
} as const;
