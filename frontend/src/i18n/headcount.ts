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
    en: `This module automatically displays the names, functions, SCIPERs, and FTE values of your unit’s members as of the reference year. Please note that the professional functions displayed in this module are categorized based on the Switzerland's classifications for universities integrated within our HR system. For student contributions, please manually add their total accumulated FTE over the year.  
The total number of FTEs is used to generate the indicators for the additional categories (Food, Commuting, and Waste), as well as the total carbon footprint per FTE for your unit. 

For more information &rarr User Guide [headcount](https://epfl-enac.github.io/co2-calculator-user-doc/headcount/) and [additional categories ](https://epfl-enac.github.io/co2-calculator-user-doc/additional-categories/)`,
    fr: `Ce module affiche automatiquement les noms, fonctions, SCIPERs et valeurs EPT des membres de votre unité pour l'année de référence. Veuillez noter que les fonctions professionnelles affichées sont catégorisées sur la base des classifications dans le système d’information universitaire suisse intégrées dans notre système RH. Pour les contributions des étudiant·e·s, veuillez ajouter manuellement leur EPT total sur l'ensemble de l'année.  
Le nombre total d'EPT est utilisé pour générer les indicateurs des catégories additionnelles (Alimentation, Pendularité et Déchets), ainsi que l'empreinte carbone totale par EPT pour votre unité.

Pour plus d'information &rarr Documentation utilisation [personnel](https://epfl-enac.github.io/co2-calculator-user-doc/fr/headcount/), et [catégories additionnelles](https://epfl-enac.github.io/co2-calculator-user-doc/fr/additional-categories/)`,
  },
  [`${MODULES.Headcount}-member`]: {
    en: 'Member| Members',
    fr: 'Membre| Membres',
  },
  [`${MODULES.Headcount}-student`]: {
    en: 'Student| Students',
    fr: 'Étudiant| Étudiant·e·s',
  },
  [`${MODULES.Headcount}-member-table-title`]: {
    en: 'Member ({count})| Members ({count})',
    fr: 'Membre ({count})| Membres ({count})',
  },
  [`${MODULES.Headcount}-student-table-title`]: {
    en: 'Students',
    fr: 'Étudiant·e·s',
  },

  [`${MODULES.Headcount}-student-table-title-info-label`]: {
    en: 'Students table information',
    fr: 'Informations sur le tableau des étudiant·e·s',
  },
  [`${MODULES.Headcount}-charts-title`]: {
    en: 'FTE per function',
    fr: 'EPT par fonction',
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
    fr: 'Ajouter un EPT étudiant·e',
  },
  // module member

  [`${MODULES.Headcount}-member-form-field-fte-label`]: {
    en: 'Full-Time Equivalent (FTE)',
    fr: 'Équivalent plein-temps (EPT)',
  },
  [`${MODULES.Headcount}-member-form-field-function-label`]: {
    en: 'Function',
    fr: 'Fonction',
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
    fr: 'EPT étudiant·e·s total',
  },
  [`${MODULES.Headcount}-student-form-title`]: {
    en: 'Add Student FTE',
    fr: 'Ajouter un EPT étudiant·e',
  },

  [`${MODULES.Headcount}-student-form-subtitle`]: {
    en: 'Enter the aggregated student FTE for your unit over the year.',
    fr: 'Entrez l’EPT étudiant·e agrégé pour votre unité sur l’année.',
  },

  [`${MODULES.Headcount}-student-form-title-info-label`]: {
    en: 'fte student tooltip',
    fr: 'info-bulle étudiant·e EPT',
  },
  'headcount-member-function-required': {
    en: 'Function is required',
    fr: 'La fonction est obligatoire',
  },
  'headcount-member-error-duplicate-uid': {
    en: "This user's {label} already exists.",
    fr: 'Le {label} de cet utilisateur existe déjà.',
  },
  headcount_student: {
    en: 'Student',
    fr: 'Étudiant·e',
  },
  headcount_professor: {
    en: 'Professor',
    fr: 'Professeur·e',
  },
  headcount_scientific_collaborator: {
    en: 'Scientific Collaborator',
    fr: 'Collaborateur·rice scientifique',
  },
  headcount_postdoctoral_researcher: {
    en: 'Postdoctoral Researcher',
    fr: 'Chercheur·e postdoctoral',
  },
  headcount_postdoctoral_assistant: {
    en: 'Postdoctoral Assistant',
    fr: 'Assistant·e postdoctoral·e',
  },
  headcount_doctoral_assistant: {
    en: 'Doctoral Assistant',
    fr: 'Assistant·e doctorant·e',
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
