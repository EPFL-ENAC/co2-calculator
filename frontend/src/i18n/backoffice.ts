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
  data_management_reporting_year: {
    en: 'Reporting Year',
    fr: 'Année de rapport',
  },
  data_management_reporting_year_hint: {
    en: 'Select the year to view module completion data for that reporting period.',
    fr: "Sélectionnez l'année pour afficher les données d'achèvement du module pour cette période de rapport.",
  },
  data_management_annual_data_import: {
    en: 'Annual Data Import',
    fr: 'Importation annuelle des données',
  },
  data_management_annual_data_import_hint: {
    en: 'Annual import of emission factors and other data necessary for CO2-eq calculation (equipment lists, coefficients, etc.) via CSV data import interfaces.',
    fr: "Importation annuelle des facteurs d'émission et d'autres données nécessaires au calcul du CO2-éq (listes d'équipements, coefficients, etc.) via des interfaces d'importation de données CSV.",
  },
  data_management_data_imports_count: {
    en: 'Data Imports ({count})',
    fr: 'Importations de données ({count})',
  },
  data_management_category: {
    en: 'Category',
    fr: 'Catégorie',
  },
  data_management_description: {
    en: 'Description',
    fr: 'Description',
  },
  data_management_factor: {
    en: 'Factor',
    fr: 'Facteur',
  },
  data_management_data: {
    en: 'Data',
    fr: 'Données',
  },
  data_management_download_csv_templates: {
    en: 'Download CSV Templates',
    fr: 'Télécharger les modèles CSV',
  },
  data_management_upload_csv_files: {
    en: 'Upload CSV Files',
    fr: 'Téléverser les fichiers CSV',
  },
  data_management_connect_api: {
    en: 'Connect API',
    fr: "Connecter l'API",
  },
  data_management_copy_previous_year: {
    en: 'Copy Previous Year',
    fr: "Copier l'année précédente",
  },
  data_management_no_data: {
    en: 'No data available for this year.',
    fr: 'Aucune donnée disponible pour cette année.',
  },
  documentation_editing_translation_title: {
    en: 'Translation',
    fr: '',
  },
  documentation_editing_translation_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_documentation_title: {
    en: 'Documentation',
    fr: '',
  },
  documentation_editing_documentation_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_calculator_co2_documentation_title: {
    en: 'CO₂ Calculator Documentation',
    fr: '',
  },
  documentation_editing_calculator_co2_documentation_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },

  documentation_editing_calculator_backoffice_documentation_title: {
    en: 'Backoffice Documentation',
    fr: '',
  },
  documentation_editing_calculator_backoffice_documentation_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_calculator_service_documentation_title: {
    en: 'Service Documentation',
    fr: '',
  },
  documentation_editing_calculator_service_documentation_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_calculator_developer_documentation_title: {
    en: 'Developer Documentation',
    fr: '',
  },
  documentation_editing_calculator_developer_documentation_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_table_label_topic: {
    en: 'Topic',
    fr: '',
  },
  documentation_editing_table_label_description: {
    en: 'Description',
    fr: '',
  },
  documentation_editing_table_label_documentation: {
    en: 'Documentation',
    fr: '',
  },
  documentation_editing_edit_on_github: {
    en: 'Edit on GitHub',
    fr: '',
  },

  documentation_editing_lorem_rows_topic: {
    en: 'Lorem Ipsum',
    fr: '',
  },
  documentation_editing_lorem_rows_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu.',
    fr: '',
  },
  documentation_editing_rows_common_topic: {
    en: 'Common',
    fr: '',
  },
  documentation_editing_rows_common_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_my_lab_topic: {
    en: 'My Lab',
    fr: '',
  },
  documentation_editing_rows_my_lab_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_professional_travel_topic: {
    en: 'Professional Travel',
    fr: '',
  },
  documentation_editing_rows_professional_travel_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_infrastructure_topic: {
    en: 'Infrastructure',
    fr: '',
  },
  documentation_editing_rows_infrastructure_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_equipment_electric_consumption_topic: {
    en: 'Equipment Electric Consumption',
    fr: '',
  },
  documentation_editing_rows_equipment_electric_consumption_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_purchase_topic: {
    en: 'Purchase',
    fr: '',
  },
  documentation_editing_rows_purchase_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_internal_services_topic: {
    en: 'Internal Services',
    fr: '',
  },
  documentation_editing_rows_internal_services_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_external_cloud_topic: {
    en: 'External Cloud',
    fr: '',
  },
  documentation_editing_rows_external_cloud_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_backoffice_topic: {
    en: 'Backoffice',
    fr: '',
  },
  documentation_editing_rows_backoffice_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  documentation_editing_rows_admin_topic: {
    en: 'Admin',
    fr: '',
  },
  documentation_editing_rows_admin_description: {
    en: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque aliquet scelerisque arcu, ac semper tortor posuere vel.',
    fr: '',
  },
  backoffice_reporting_year_title: {
    en: 'Reporting Year',
    fr: '',
  },
  backoffice_reporting_year_description: {
    en: 'Select the year to view module completion data for that reporting period.',
    fr: '',
  },
  backoffice_reporting_module_status_label: {
    en: 'Filter by Modules Status ({count})',
    fr: '',
  },
  backoffice_reporting_all_modules: {
    en: 'All Modules',
    fr: '',
  },
  backoffice_reporting_select_all: {
    en: 'Select All',
    fr: '',
  },
  backoffice_reporting_unselect_all: {
    en: 'Unselect All',
    fr: '',
  },
  backoffice_reporting_generate_report_title: {
    en: 'Export Report',
    fr: '',
  },
  backoffice_reporting_generate_report_description: {
    en: 'Generate your report and export in your preferred format.',
    fr: '',
  },
  backoffice_reporting_row_module_label: {
    en: 'Module',
    fr: '',
  },
  backoffice_reporting_row_status_label: {
    en: 'Status',
    fr: '',
  },
  backoffice_reporting_row_outlier_values_label: {
    en: 'Outlier Values',
    fr: '',
  },
  backoffice_reporting_select_year: {
    en: 'Select Year',
    fr: '',
  },
  backoffice_reporting_modules_label: {
    en: 'Modules ({count})',
    fr: '',
  },
  backoffice_reporting_errors_label: {
    en: 'Errors',
    fr: '',
  },
  backoffice_reporting_filter_units_label: {
    en: 'Units',
    fr: '',
  },
  backoffice_reporting_row_completion_label: {
    en: 'Completion',
    fr: '',
  },
  backoffice_reporting_row_unit_label: {
    en: 'Unit',
    fr: '',
  },
  backoffice_reporting_row_affiliation_label: {
    en: 'Affiliation',
    fr: '',
  },
  backoffice_reporting_row_principal_user_label: {
    en: 'Principal User',
    fr: '',
  },
  backoffice_reporting_row_last_update_label: {
    en: 'Last Update',
    fr: '',
  },
  backoffice_reporting_row_action_label: {
    en: 'Action',
    fr: '',
  },
  backoffice_reporting_units_status_label: {
    en: 'Units ({count})',
    fr: '',
  },
  backoffice_reporting_generate_usage_title: {
    en: 'Usage',
    fr: '',
  },
  backoffice_reporting_generate_usage_description: {
    en: 'Reports on calculator utilization: which laboratories have completed modules, user activity, data entry status, and completion rates.',
    fr: '',
  },
  backoffice_reporting_generate_results_title: {
    en: 'Results',
    fr: '',
  },
  backoffice_reporting_generate_results_description: {
    en: 'CO2-eq calculations with visual graphs and charts showing module completion, laboratory activity, and emissions breakdowns.',
    fr: '',
  },
  backoffice_reporting_generate_combined_title: {
    en: 'Combined',
    fr: '',
  },
  backoffice_reporting_generate_combined_description: {
    en: 'Comprehensive report including both usage statistics and CO2-eq results, ideal for executive summaries and annual reporting.',
    fr: '',
  },
  backoffice_reporting_csv_validated: {
    en: 'Validated',
    fr: '',
  },
  backoffice_reporting_csv_in_progress: {
    en: 'In Progress',
    fr: '',
  },
  backoffice_reporting_csv_default: {
    en: 'Not Started',
    fr: '',
  },
  backoffice_reporting_generate_formats: {
    en: 'PDF: Formatted report with charts and visualizations, ideal for presentations and sharing.\nCSV: Raw data in spreadsheet format for further analysis in Excel or other tools.',
    fr: '',
  },
  user_management_page_description: {
    en: 'User management at EPFL is handled via Accred.',
    fr: "La gestion des utilisateurs à l'EPFL est gérée via Accred.",
  },
  user_management_page_button_label: {
    en: 'Go to User management system (Accred)',
    fr: 'Accéder au système de gestion des utilisateurs (Accred)',
  },
  user_management_page_button_documentation_label: {
    en: 'Go to User management system documentation',
    fr: 'Documentation de la gestion des utilisateurs',
  },
  user_management_access_button: {
    en: 'Back-office Management',
    fr: 'Gestion du back-office',
  },
  back_to_calculator_button: {
    en: 'Back to Calculator',
    fr: 'Retour au calculateur',
  },
} as const;
