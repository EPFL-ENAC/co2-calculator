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
  [`${MODULES.MyLab}-member`]: {
    en: 'Member| Members',
    fr: 'Membre| Membres',
  },
  [`${MODULES.MyLab}-student`]: {
    en: 'Student| Students',
    fr: 'Étudiant| Étudiants',
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
  [`${MODULES.MyLab}-student-table-title-info-label`]: {
    en: 'Students table information',
    fr: 'Informations sur le tableau des étudiants',
  },
  [`${MODULES.MyLab}-student-table-title-info-tooltip`]: {
    en: 'Due to data-protection rules, students names and individual FTE are not shown automatically.',
    fr: 'En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement.',
  },
  [`${MODULES.MyLab}-charts-title`]: {
    en: 'FTE per position',
    fr: 'EPT par poste',
  },
  [`${MODULES.MyLab}-charts-no-data-message`]: {
    en: 'No data available for FTE per position.',
    fr: 'Aucune donnée disponible pour l’EPT par poste.',
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

  [`${MODULES.MyLab}-student-form-add-button`]: {
    en: 'Add Student FTE',
    fr: 'Ajouter un EPT étudiant',
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
    en: 'Add Student FTE',
    fr: 'Ajouter un EPT étudiant',
  },

  [`${MODULES.MyLab}-student-form-title-info-tooltip`]: {
    en: `Due to data-protection rules, students’ names and individual FTE are not shown automatically.`,
    fr: `En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement.te`,
  },
  [`${MODULES.MyLab}-student-form-subtitle`]: {
    en: ` Please use the Student FTE Calculator Helper below, then enter the aggregated usage time.
    `,
    fr: `Veuillez utiliser l’outil d’aide « Calculateur d’EPT Étudiants » ci-dessous, puis entrer le temps d’utilisation agrégé.`,
  },
  [`${MODULES.MyLab}-student-student-helper-title`]: {
    en: 'Student FTE Calculator Helper',
    fr: 'EPT étudiants - Outil d’aide au calcul',
  },
  [`${MODULES.MyLab}-member-form-title-info-label`]: {
    en: 'fte member tooltip',
    fr: 'info-bulle membre EPT',
  },
  [`${MODULES.MyLab}-member-form-title-info-tooltip`]: {
    en: 'lorem ipsum',
    fr: 'Texte d’exemple',
  },

  student_helper_title: {
    en: 'Student FTE Calculator Helper',
    fr: 'EPT étudiants - Outil d’aide au calcul',
  },

  student_helper_students_label: {
    en: 'Number of students',
    fr: "Nombre d'étudiant·es",
  },
  student_helper_duration_label: {
    en: 'Average duration (months)',
    fr: 'Durée moyenne (mois)',
  },
  student_helper_avg_fte_label: {
    en: 'Average FTE per student',
    fr: 'EPT moyen par étudiant·e',
  },
  student_helper_calculated_label: {
    en: 'Total Student FTE',
    fr: 'EPT annuel calculé',
  },
  student_helper_use_button: {
    en: 'Update',
    fr: 'Mettre à jour',
  },
  [`${MODULES.MyLab}-student-form-title-info-label`]: {
    en: 'fte student tooltip',
    fr: 'info-bulle étudiant EPT',
  },
  [`${MODULES.MyLab}-student-form-title-info-tooltip`]: {
    en: 'lorem ipsum',
    fr: 'Texte d’exemple',
  },
  app_headcount_student_helper_students_error: {
    en: 'Please enter a valid number of students (greater than 0).',
    fr: "Veuillez entrer un nombre valide d'étudiants (supérieur à 0).",
  },
  app_headcount_student_helper_duration_error: {
    en: 'Duration (months) must be less than or equal to 12 and greater than 0.',
    fr: 'Durée (mois) doit être inférieure ou égale à 12 et supérieure à 0.',
  },
  app_headcount_student_helper_avg_fte_error: {
    en: 'Average FTE per student must be between 0 and 1.',
    fr: "L'EPT moyen par étudiant doit être compris entre 0 et 1.",
  },
  app_headcount_student: {
    en: 'Student',
    fr: 'Étudiant',
  },
  app_headcount_professor: {
    en: 'Professor',
    fr: 'Professeur',
  },
  app_headcount_scientific_collaborator: {
    en: 'Scientific Collaborator',
    fr: 'Collaborateur scientifique',
  },
  app_headcount_postdoctoral_researcher: {
    en: 'Postdoctoral Researcher',
    fr: 'Chercheur postdoctoral',
  },
  app_headcount_doctoral_assistant: {
    en: 'Doctoral Assistant',
    fr: 'Assistant doctorant',
  },
  app_headcount_trainee: {
    en: 'Trainee',
    fr: 'Stagiaire',
  },
  app_headcount_technical_administrative_staff: {
    en: 'Technical/Administrative Staff',
    fr: 'Personnel technique/administratif',
  },
  app_headcount_other: {
    en: 'Other',
    fr: 'Autre',
  },
} as const;
