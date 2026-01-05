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
    en: 'Data Management',
    fr: 'Gestion des données',
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
    en: 'backoffice-documentation-editing-description',
    fr: 'backoffice-documentation-editing-description',
  },
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName]: {
    en: 'Reporting',
    fr: 'Rapports',
  },
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.description]: {
    en: 'backoffice-reporting-description',
    fr: 'backoffice-reporting-description',
  },
  back_to_calculator_button: {
    en: 'Back to Calculator',
    fr: 'Retour au calculateur',
  },
} as const;
