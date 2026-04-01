export default {
  backoffice_data_management_title: {
    en: 'Data Management',
    fr: 'Gestion des données',
  },
  'backoffice-data-management-description': {
    en: 'Manage and configure data imports, emission factors, and module settings for CO₂ calculations.',
    fr: "Gérer et configurer les importations de données, les facteurs d'émission et les paramètres des modules pour les calculs de CO₂.",
  },
  DATA_ENTRIES: {
    en: 'Data Entries',
    fr: 'Saisies de données',
  },
  FACTORS: {
    en: 'Factors',
    fr: 'Facteurs',
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
    en: 'Annual import of emission factors and other data necessary for CO₂-eq calculation (equipment lists, coefficients, etc.) via CSV data import interfaces. All data formats are detailed in the back-office Guide.',
    fr: "Importation annuelle des facteurs d'émission et d'autres données nécessaires au calcul du CO₂-éq (listes d'équipements, coefficients, etc.) via des interfaces d'importation de données CSV. Tous les formats de données sont détaillés dans le Guide du back-office.",
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
  data_management_upload: {
    en: 'Upload',
    fr: 'Téléverser',
  },
  data_management_supported_file_types: {
    en: 'Supported file types: .csv',
    fr: 'Types de fichiers pris en charge : .csv',
  },
  data_management_no_temp_files_uploaded: {
    en: 'No temporary files uploaded.',
    fr: "Aucun fichier temporaire n'a été téléversé.",
  },
  data_management_temp_files_uploaded: {
    en: 'Temporary files uploaded: {count}',
    fr: 'Fichiers temporaires téléversés : {count}',
  },
  data_management_delete_temp_files: {
    en: 'Delete Temporary Files',
    fr: 'Supprimer les fichiers temporaires',
  },
  data_management_column_other: {
    en: 'Other',
    fr: 'Autre',
  },
  data_management_no_data_warning: {
    en: 'No data uploaded. Only user inputs will be considered.',
    fr: 'Aucune donnée téléversée. Seules les saisies utilisateur seront prises en compte.',
  },
  data_management_no_factors_error: {
    en: 'No factors uploaded. Please upload factors.',
    fr: 'Aucun facteur téléversé. Veuillez téléverser les facteurs.',
  },
  data_management_tbd: {
    en: 'Coming soon',
    fr: 'Bientôt disponible',
  },
  data_management_other_train_stations: {
    en: 'Locations train-station',
    fr: 'Localisations gare',
  },
  data_management_other_airports: {
    en: 'Location airport',
    fr: 'Localisations aéroport',
  },
  data_management_other_institution_rooms: {
    en: 'Institution rooms',
    fr: "Salles de l'institution",
  },
  data_management_upload_reference: {
    en: 'Upload Reference',
    fr: 'Téléverser référence',
  },
  // Data entry dialog
  data_management_add_data: {
    en: 'Add Data',
    fr: 'Ajouter des données',
  },
  data_management_reupload_data: {
    en: 'ReUpload Data',
    fr: 'Re-téléverser des données',
  },
  data_management_add_factors: {
    en: 'Add Factors',
    fr: 'Ajouter des facteurs',
  },
  data_management_reupload_factors: {
    en: 'ReUpload Factors',
    fr: 'Re-téléverser des facteurs',
  },
  data_management_import_title: {
    en: 'Import {type}',
    fr: 'Importer {type}',
  },
  data_management_tab_upload_csv: {
    en: 'Upload CSV',
    fr: 'Téléverser CSV',
  },
  data_management_tab_connect_api: {
    en: 'Connect API',
    fr: 'Connecter API',
  },
  data_management_tab_copy_previous: {
    en: 'Copy from Previous Year',
    fr: "Copier de l'année précédente",
  },
  data_management_api_server_url: {
    en: 'Server URL',
    fr: 'URL du serveur',
  },
  data_management_api_client_id: {
    en: 'Client ID',
    fr: 'ID client',
  },
  data_management_api_secret_id: {
    en: 'Secret ID',
    fr: 'ID du secret',
  },
  data_management_api_secret_value: {
    en: 'Secret Value',
    fr: 'Valeur du secret',
  },
  data_management_api_test_connection: {
    en: 'Test Connection',
    fr: 'Tester la connexion',
  },
  data_management_api_connect_and_sync: {
    en: 'Connect & Sync',
    fr: 'Connecter et synchroniser',
  },
  data_management_copy_from_year: {
    en: 'Copy from {year}',
    fr: 'Copier de {year}',
  },
  data_management_select_import: {
    en: 'Select import to copy',
    fr: "Sélectionner l'import à copier",
  },
  data_management_copy_start: {
    en: 'Start Copy',
    fr: 'Démarrer la copie',
  },
  data_management_no_previous_jobs: {
    en: 'No successful imports from previous year',
    fr: "Aucune importation réussie de l'année précédente",
  },
  data_management_connection_success: {
    en: 'Connection successful',
    fr: 'Connexion réussie',
  },
  data_management_connection_failed: {
    en: 'Connection failed',
    fr: 'Connexion échouée',
  },
  data_management_copy_failed: {
    en: 'Failed to copy from previous year',
    fr: "Échec de la copie de l'année précédente",
  },
  data_management_last_import_date: {
    en: 'Last import',
    fr: 'Dernier import',
  },
  data_management_rows_imported: {
    en: 'rows imported',
    fr: 'lignes importées',
  },
  data_management_download_last_csv: {
    en: 'Download last CSV',
    fr: 'Télécharger le dernier CSV',
  },
  data_management_sync_units_from_accred: {
    en: 'Sync Units from Accred',
    fr: 'Synchroniser les unités depuis Accred',
  },
  data_management_unit_sync_started: {
    en: 'Unit sync started',
    fr: 'Synchronisation des unités démarrée',
  },
  data_management_unit_sync_started_caption: {
    en: 'This may take a few minutes...',
    fr: 'Cela peut prendre quelques minutes...',
  },
  data_management_unit_sync_success: {
    en: 'Units synced successfully!',
    fr: 'Unités synchronisées avec succès !',
  },
  data_management_unit_sync_success_caption: {
    en: 'All units and principal users have been updated',
    fr: 'Toutes les unités et utilisateurs principaux ont été mis à jour',
  },
  data_management_unit_sync_error: {
    en: 'Unit sync failed',
    fr: 'La synchronisation des unités a échoué',
  },
  data_management_unit_sync_error_caption: {
    en: 'Please try again later',
    fr: 'Veuillez réessayer plus tard',
  },
  data_management_last_upload_overwrite: {
    en: 'The last uploaded data will be overwritten',
    fr: 'Les dernières données téléversées seront écrasées',
  },
  data_management_year_not_configured: {
    en: 'Year {year} is not configured yet',
    fr: "L'année {year} n'est pas encore configurée",
  },
  data_management_year_not_configured_hint: {
    en: 'Create the year configuration to start managing data for this reporting period.',
    fr: 'Créez la configuration annuelle pour commencer à gérer les données de cette période.',
  },
  data_management_create_year: {
    en: 'Create year {year}',
    fr: "Créer l'année {year}",
  },
  data_management_year_created: {
    en: 'Year {year} configuration created',
    fr: "Configuration de l'année {year} créée",
  },
  data_management_year_status_enabled: {
    en: 'Year {year} is enabled — users can access their modules',
    fr: "L'année {year} est activée — les utilisateurs peuvent accéder à leurs modules",
  },
  data_management_year_status_disabled: {
    en: 'Year {year} is disabled — only backoffice managers can access this page',
    fr: "L'année {year} est désactivée — seuls les gestionnaires backoffice peuvent accéder à cette page",
  },
  data_management_year_enable: {
    en: 'Enable',
    fr: 'Activer',
  },
  data_management_year_disable: {
    en: 'Disable',
    fr: 'Désactiver',
  },
  data_management_year_enabled: {
    en: 'Year {year} enabled',
    fr: "Année {year} activée",
  },
  data_management_year_disabled: {
    en: 'Year {year} disabled',
    fr: "Année {year} désactivée",
  },
} as const;
