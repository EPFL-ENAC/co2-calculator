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
  threshold_fixed_title: {
    en: 'Fixed Threshold',
    fr: 'Seuil fixe',
  },
  threshold_fixed_description: {
    en: 'Apply a single fixed threshold value across all items.',
    fr: 'Appliquer une valeur de seuil fixe unique à tous les éléments.',
  },
  threshold_fixed_value: {
    en: 'Threshold value',
    fr: 'Valeur du seuil',
  },
  threshold_fixed_summary: {
    en: 'Using fixed threshold: {value}',
    fr: 'Seuil fixe utilisé : {value}',
  },

  threshold_median_title: {
    en: 'Median Threshold',
    fr: 'Seuil médian',
  },
  threshold_median_description: {
    en: 'Compute the threshold from the median of current dataset.',
    fr: 'Calculer le seuil à partir de la médiane du jeu de données actuel.',
  },
  threshold_median_info: {
    en: 'Median is recalculated when data changes.',
    fr: 'La médiane est recalculée lorsque les données changent.',
  },
  threshold_median_summary: {
    en: 'Using median threshold: {value}',
    fr: 'Seuil médian utilisé : {value}',
  },

  threshold_top_title: {
    en: 'Top-N Threshold',
    fr: 'Seuil Top-N',
  },
  threshold_top_description: {
    en: 'Keep only the top N items by value; others are below threshold.',
    fr: 'Conserver uniquement les N éléments les plus élevés ; les autres sont sous le seuil.',
  },
  threshold_top_value: {
    en: 'N value',
    fr: 'Valeur N',
  },
  threshold_top_summary: {
    en: 'Using top-N threshold: {value}',
    fr: 'Seuil Top-N utilisé : {value}',
  },
} as const;
