import { MODULES } from 'src/constant/modules';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';

export default {
  [MODULES.Headcount]: {
    en: 'Headcount',
    fr: 'Personnel',
  },
  [`${MODULES.Headcount}-description`]: {
    en: 'Verify team members and Full Time Equivalent (FTE) values for your unit',
    fr: 'Vérifiez les membres de l’équipe et leurs équivalents plein-temps (EPT) pour votre unité',
  },
  [`${MODULES.Headcount}-title-subtext`]: {
    en: `This module automatically displays the names, roles, and FTE values of your unit’s personnel as of the end of the year. Review and make any necessary adjustments to ensure your team profile is complete. For student contributions, use the integrated Student FTE Calculator Helper to add their total FTE over the year.`,
    fr: `Ce module affiche automatiquement les noms, rôles et EPT des membres de votre unité à la fin de l’année. Passez en revue ces informations et apportez les ajustements nécessaires pour garantir que le profil de votre équipe soit complet. Pour les contributions des étudiants, utilisez l’outil intégré Calculateur d’EPT étudiants afin d’ajouter leur EPT total sur l’année.`,
  },
  [`${MODULES.Headcount}-title-tooltip-title`]: {
    en: 'The total FTE is used to generate the generic indicators for Food and Commuting, as well as total carbon footprint per FTE for your unit.',
    fr: "Le nombre total d'EPT est utilisé pour générer les indicateurs génériques relatifs à l'Alimentation et au Mobilité pendulaire, ainsi que l'empreinte carbone totale par EPT pour votre unité.",
  },
  [`${MODULES.Headcount}-member`]: {
    en: 'Member| Members',
    fr: 'Membre| Membres',
  },
  [`${MODULES.Headcount}-student`]: {
    en: 'Student| Students',
    fr: 'Étudiant| Étudiants',
  },
  [`${MODULES.Headcount}-member-table-title`]: {
    en: 'Member ({count})| Members ({count})',
    fr: 'Membre ({count})| Membres ({count})',
  },
  [`${MODULES.Headcount}-student-table-title`]: {
    en: 'Students',
    fr: 'Étudiants',
  },

  [`${MODULES.Headcount}-member-table-title-info-tooltip`]: {
    en: 'You can add data one at a time using the Add FTE below, or upload several entries at once using a file that follows the template.',
    fr: 'Vous pouvez ajouter les données une par une en utilisant le bouton « Ajouter un EPT » ci-dessous, ou importer plusieurs entrées à la fois via un fichier respectant le modèle fourni.',
  },
  [`${MODULES.Headcount}-student-table-title-info-label`]: {
    en: 'Students table information',
    fr: 'Informations sur le tableau des étudiants',
  },
  [`${MODULES.Headcount}-student-table-title-info-tooltip`]: {
    en: 'Due to data-protection rules, students names and individual FTE are not shown automatically.',
    fr: 'En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement.',
  },
  [`${MODULES.Headcount}-charts-title`]: {
    en: 'FTE per position',
    fr: 'EPT par poste',
  },
  [`${MODULES.Headcount}-charts-no-data-message`]: {
    en: 'No data available for FTE per position.',
    fr: 'Aucune donnée disponible pour l’EPT par poste.',
  },
  [`${MODULES.Headcount}-member-form-title`]: {
    // en: 'Add Full-Time Equivalent member',
    // fr: 'Ajouter un membre à équivalent plein-temps',
    en: 'Add FTE',
    fr: 'Ajouter un EPT',
  },
  [`${MODULES.Headcount}-member-form-title`]: {
    // en: 'Add Full-Time Equivalent member',
    // fr: 'Ajouter un membre à équivalent plein-temps',
    en: 'Add FTE',
    fr: 'Ajouter un EPT',
  },

  [`${MODULES.Headcount}-student-form-add-button`]: {
    en: 'Add Student FTE',
    fr: 'Ajouter un EPT étudiant',
  },
  // module member

  [`${MODULES.Headcount}-member-form-field-fte-label`]: {
    en: 'Full-Time Equivalent (FTE)',
    fr: 'Équivalent plein-temps (EPT)',
  },
  [`${MODULES.Headcount}-member-form-field-position-label`]: {
    en: 'Position',
    fr: 'Position',
  },
  [`${MODULES.Headcount}-member-form-field-position-category-label`]: {
    en: 'Position',
    fr: 'Position',
  },
  [`${MODULES.Headcount}-member-form-field-name-label`]: {
    en: 'Name',
    fr: 'Nom',
  },
  [`${MODULES.Headcount}-member-form-field-user-institutional-id-label`]: {
    en: INSTITUTIONAL_ID_LABEL,
    fr: INSTITUTIONAL_ID_LABEL,
  },
  // module_mylab_student_form_field_fte_label
  [`${MODULES.Headcount}-student_form_field_fte_label`]: {
    en: 'Total Student FTE',
    fr: 'EPT étudiants total',
  },
  [`${MODULES.Headcount}-student-form-title`]: {
    en: 'Add Student FTE',
    fr: 'Ajouter un EPT étudiant',
  },

  [`${MODULES.Headcount}-student-form-title-info-tooltip`]: {
    en: `Due to data-protection rules, students’ names and individual FTE are not shown automatically.`,
    fr: `En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement.`,
  },
  [`${MODULES.Headcount}-student-form-subtitle`]: {
    en: 'Enter the aggregated student FTE for your unit over the year.',
    fr: 'Entrez l’EPT étudiant agrégé pour votre unité sur l’année.',
  },
  [`${MODULES.Headcount}-member-form-title-info-label`]: {
    en: 'fte member tooltip',
    fr: 'info-bulle membre EPT',
  },
  [`${MODULES.Headcount}-member-form-title-info-tooltip`]: {
    en: 'lorem ipsum',
    fr: 'Texte d’exemple',
  },

  [`${MODULES.Headcount}-student-form-title-info-label`]: {
    en: 'fte student tooltip',
    fr: 'info-bulle étudiant EPT',
  },
  [`${MODULES.Headcount}-student-form-title-info-tooltip`]: {
    en: 'lorem ipsum',
    fr: 'Texte d’exemple',
  },
  'headcount-member-error-duplicate-uid': {
    en: "This user's {label} already exists.",
    fr: 'Le {label} de cet utilisateur existe déjà.',
  },
  headcount_student: {
    en: 'Student',
    fr: 'Étudiant',
  },
  headcount_professor: {
    en: 'Professor',
    fr: 'Professeur',
  },
  headcount_scientific_collaborator: {
    en: 'Scientific Collaborator',
    fr: 'Collaborateur scientifique',
  },
  headcount_postdoctoral_researcher: {
    en: 'Postdoctoral Researcher',
    fr: 'Chercheur postdoctoral',
  },
  headcount_postdoctoral_assistant: {
    en: 'Postdoctoral Assistant',
    fr: 'Assistant postdoctoral',
  },
  headcount_doctoral_assistant: {
    en: 'Doctoral Assistant',
    fr: 'Assistant doctorant',
  },
  headcount_trainee: {
    en: 'Trainee',
    fr: 'Stagiaire',
  },
  headcount_technical_administrative_staff: {
    en: 'Technical/Administrative Staff',
    fr: 'Personnel technique/administratif',
  },
  headcount_other: {
    en: 'Other',
    fr: 'Autre',
  },
} as const;
