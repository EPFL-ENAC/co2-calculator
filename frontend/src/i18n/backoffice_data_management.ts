export default {
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
    en: 'Annual import of emission factors and other data necessary for CO₂-eq calculation (equipment lists, coefficients, etc.) via CSV data import interfaces.',
    fr: "Importation annuelle des facteurs d'émission et d'autres données nécessaires au calcul du CO₂-éq (listes d'équipements, coefficients, etc.) via des interfaces d'importation de données CSV.",
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
} as const;
