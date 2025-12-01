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
  backoffice_reporting_year_title: {
    en: 'Select Year for Report',
    fr: "Sélectionner l'année pour le rapport",
  },
  backoffice_reporting_year_description: {
    en: 'Choose the assessment year for which you want to generate the report.',
    fr: "Choisissez l'année d'évaluation pour laquelle vous souhaitez générer le rapport.",
  },
  backoffice_reporting_row_unit_label: {
    en: 'Unit',
    fr: 'Unité',
  },
  backoffice_reporting_row_units_label: {
    en: 'Units',
    fr: 'Unités',
  },
  backoffice_reporting_row_affiliation_label: {
    en: 'Affiliation',
    fr: 'Affiliation',
  },
  backoffice_reporting_row_completion_label: {
    en: 'Completion',
    fr: 'Complétion',
  },
  backoffice_reporting_row_principal_user_label: {
    en: 'Principal User',
    fr: 'Utilisateur principal',
  },
  backoffice_reporting_row_last_update_label: {
    en: 'Last Update',
    fr: 'Dernière mise à jour',
  },
  backoffice_reporting_row_outlier_values_label: {
    en: 'Outlier Values',
    fr: 'Valeurs aberrantes',
  },
  backoffice_reporting_row_action_label: {
    en: 'Action',
    fr: 'Action',
  },
  backoffice_reporting_module_status_label: {
    en: 'Filter by Module Status ({count})',
    fr: 'Filtrer par statut de module ({count})',
  },
  backoffice_reporting_all_modules: {
    en: 'All',
    fr: 'Tous',
  },
  backoffice_reporting_select_all: {
    en: 'Select All',
    fr: 'Tout sélectionner',
  },
  backoffice_reporting_unselect_all: {
    en: 'Unselect All',
    fr: 'Tout désélectionner',
  },
  backoffice_reporting_units_status_label: {
    en: 'Units ({count})',
    fr: 'Unités ({count})',
  },
  backoffice_reporting_generate_report_title: {
    en: 'Export Data',
    fr: 'Exporter les données',
  },
  backoffice_reporting_generate_report_description: {
    en: 'Generate your report and export in your preferred format.',
    fr: 'Générez votre rapport et exportez-le dans le format de votre choix.',
  },
  backoffice_reporting_generate_usage_title: {
    en: 'Usage',
    fr: 'Utilisation',
  },
  backoffice_reporting_generate_usage_description: {
    en: 'Reports on calculator utilization: which laboratories have completed modules, user activity, data entry status, and completion rates.',
    fr: "Rapports sur l'utilisation du calculateur : quels laboratoires ont complété les modules, activité des utilisateurs, statut de saisie des données et taux de complétion.",
  },
  backoffice_reporting_generate_results_title: {
    en: 'Results',
    fr: 'Résultats',
  },
  backoffice_reporting_generate_results_description: {
    en: 'CO₂-eq calculations with visual graphs and charts showing module completion, laboratory activity, and emissions breakdowns.',
    fr: "Calculs CO₂-éq avec graphiques et tableaux visuels montrant la complétion des modules, l'activité des laboratoires et les répartitions des émissions.",
  },
  backoffice_reporting_generate_combined_title: {
    en: 'Combined',
    fr: 'Combiné',
  },
  backoffice_reporting_generate_combined_description: {
    en: 'Comprehensive report including both usage statistics and CO₂-eq results, ideal for executive summaries and annual reporting.',
    fr: "Rapport complet incluant à la fois les statistiques d'utilisation et les résultats CO₂-éq, idéal pour les résumés exécutifs et les rapports annuels.",
  },
  backoffice_reporting_generate_formats: {
    en: 'Export Formats: \n PDF: Formatted report with charts and visualizations, ideal for presentations and sharing. \n CSV: Raw data in spreadsheet format for further analysis in Excel or other tools.',
    fr: "Formats d'export : \n PDF : Rapport formaté avec graphiques et visualisations, idéal pour les présentations et le partage. \n CSV : Données brutes au format tableur pour une analyse plus approfondie dans Excel ou d'autres outils.",
  },
  backoffice_reporting_csv_validated: {
    en: 'Validated',
    fr: 'Validé',
  },
  backoffice_reporting_csv_in_progress: {
    en: 'In Progress',
    fr: 'En cours',
  },
  backoffice_reporting_csv_default: {
    en: 'Default',
    fr: 'Par défaut',
  },
} as const;
