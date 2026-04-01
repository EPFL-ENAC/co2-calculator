import { BACKOFFICE_NAV } from 'src/constant/navigation';

export default {
  [BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.routeName]: {
    en: 'User Management',
    fr: 'Gestion des utilisateurs',
  },
  [BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.description]: {
    en: 'backoffice-user-management-description',
    fr: 'backoffice-user-management-description',
  },
  [BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName]: {
    en: 'Configuration',
    fr: 'Configuration',
  },
  [BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.description]: {
    en: 'backoffice-data-management-description',
    fr: 'backoffice-data-management-description',
  },
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.routeName]: {
    en: 'Documentation Editing',
    fr: 'Édition de la documentation',
  },
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.description]: {
    en: 'Manage and update documentation and translation files.',
    fr: 'Gérer et mettre à jour la documentation et les fichiers de traduction.',
  },
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName]: {
    en: 'Reporting',
    fr: 'Rapports',
  },
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.description]: {
    en: 'backoffice-reporting-description',
    fr: 'backoffice-reporting-description',
  },
  [BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING.routeName]: {
    en: 'UI Texts Editing',
    fr: 'Édition des textes UI',
  },
  [BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING.description]: {
    en: 'Edit UI translation files for all modules.',
    fr: 'Modifier les fichiers de traduction UI pour tous les modules.',
  },
  [BACKOFFICE_NAV.BACKOFFICE_LOGS.routeName]: {
    en: 'Logs',
    fr: 'Journaux',
  },
  [BACKOFFICE_NAV.BACKOFFICE_LOGS.description]: {
    en: 'View system audit logs. Superadmin access only.',
    fr: "Consulter les journaux d'audit. Accès superadmin uniquement.",
  },
  back_to_calculator_button: {
    en: 'Back to Calculator',
    fr: 'Retour au calculateur',
  },
} as const;
