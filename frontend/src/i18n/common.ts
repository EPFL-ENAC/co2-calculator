import { ROLES } from 'src/constant/roles';
import { MODULES } from 'src/constant/modules';

export default {
  logo_alt: {
    en: 'Logo EPFL',
    fr: 'Logo EPFL',
  },
  calculator_title: {
    en: 'CO₂ Calculator',
    fr: 'CO₂ Calculator',
  },
  home: {
    en: 'Home',
    fr: 'Home',
  },
  module: {
    en: 'Module',
    fr: 'Module',
  },
  'module-results': {
    en: 'Module Results',
    fr: 'Résultats du Module',
  },
  results: {
    en: 'Results',
    fr: 'Résultats',
  },
  simulations: {
    en: 'Simulations',
    fr: 'Simulations',
  },
  'simulation-add': {
    en: 'Add Simulation',
    fr: 'Ajouter une Simulation',
  },
  'simulation-edit': {
    en: 'Edit Simulation',
    fr: 'Modifier la Simulation',
  },
  documentation: {
    en: 'Documentation',
    fr: 'Documentation',
  },
  logout: {
    en: 'Logout',
    fr: 'Se déconnecter',
  },
  tco2eq: {
    en: 't CO₂-eq',
    fr: 't CO₂-eq',
  },
  [ROLES.StandardUser]: {
    en: 'User',
    fr: 'Utilisateur',
  },
  [ROLES.PrincipalUser]: {
    en: 'Unit Manager',
    fr: "Responsable d'unité",
  },
  [ROLES.BackOfficeMetier]: {
    en: 'Backoffice Administrator',
    fr: 'Administrateur métier',
  },
  [ROLES.SuperAdmin]: {
    en: 'Super Admin',
    fr: 'Super Admin',
  },
  info_with_link: {
    en: '<span>For more information, visit <a href="{url}" target="_blank">{linkText}</a>.</span>',
    fr: '<span>Pour plus d\'informations, visitez <a href="{url}" target="_blank">{linkText}</a>.</span>',
  },
  documentation_link: {
    en: 'Documentation and Resources',
    fr: 'Documentation et Ressources',
  },
  contact: {
    en: 'Contact',
    fr: 'Contact',
  },
  unit_carbon_footprint_title: {
    en: 'My Unit Carbon Footprint',
    fr: "Mon Empreinte Carbone de l'unité",
  },
  module_total_result_title: {
    en: ({ named }) => {
      if (named('type') === MODULES.MyLab) {
        return 'Total FTE';
      }
      if (named('typeI18n')) {
        return `Total ${named('typeI18n')} Carbon Footprint`;
      }
      return 'Total Carbon Footprint';
    },
    fr: ({ named }) => {
      if (named('type') === MODULES.MyLab) {
        return 'Total ETP';
      }
      if (named('typeI18n')) {
        return `Empreinte Carbone ${named('typeI18n')}`;
      }
      return 'Empreinte Carbone Totale';
    },
  },
  module_total_result_title_unit: {
    en: ({ named }) => {
      if (named('type') === MODULES.MyLab) {
        return 'FTE';
      }
      return 't CO₂-eq';
    },
    fr: ({ named }) => {
      if (named('type') === MODULES.MyLab) {
        return 'ETP';
      }
      return 't CO₂-eq';
    },
  },
  module_total_result_placeholder: {
    en: 'Work in progress, validate to see the results.',
    fr: "En cours jusqu'à validation.",
  },
  common_filter_all: {
    en: 'All',
    fr: 'Tous',
  },
  common_filter_yes: {
    en: 'Yes',
    fr: 'Oui',
  },
  common_filter_no: {
    en: 'No',
    fr: 'Non',
  },
  common_filter_complete: {
    en: 'Complete',
    fr: 'Complet',
  },
  common_filter_incomplete: {
    en: 'Incomplete',
    fr: 'Incomplet',
  },
  common_filters_search_label: {
    en: 'Search',
    fr: 'Rechercher',
  },
  common_search_placeholder: {
    en: 'Search rows',
    fr: 'Rechercher dans le tableau',
  },
  common_show_all_rows: {
    en: 'View Full Table',
    fr: 'Voir tout',
  },
  common_no_results: {
    en: 'No results',
    fr: 'Aucun résultat',
  },
  common_export_as_pdf: {
    en: 'Export as PDF',
    fr: 'Exporter en PDF',
  },
  common_upload_csv: {
    en: 'Upload CSV',
    fr: 'Importer CSV',
  },
  common_download_as_png: {
    en: 'PNG',
    fr: 'PNG',
  },
  common_download_as_csv: {
    en: 'CSV',
    fr: 'CSV',
  },
  common_download_csv_template: {
    en: 'Download CSV Template',
    fr: 'Télécharger le modèle CSV',
  },
  common_upload_csv_mock: {
    en: 'CSV upload coming soon (mocked UI only)',
    fr: 'Import CSV à venir (interface simulée)',
  },
  common_download_csv_template_mock: {
    en: 'CSV template download (mocked)',
    fr: 'Téléchargement du modèle CSV (simulé)',
  },
  common_export_as_csv: {
    en: 'Export as CSV',
    fr: 'Exporter en CSV',
  },
  documentation_button_label: {
    en: 'Documentation',
    fr: 'Documentation',
  },
  documentation_backoffice_button_label: {
    en: 'Back-office Documentation',
    fr: 'Documentation Back-office',
  },
  documentation_dev_button_label: {
    en: 'Developer Documentation',
    fr: 'Documentation Développeur',
  },
  common_add_button: {
    en: 'Add',
    fr: 'Ajouter',
  },
  common_update_button: {
    en: 'Update',
    fr: 'Mettre à jour',
  },
  common_add_with_note_button: {
    en: 'Add with note',
    fr: 'Ajouter avec note',
  },
  common_actions: {
    en: 'Actions',
    fr: 'Actions',
  },
  common_validate: {
    en: 'Validate Module',
    fr: 'Valider le module',
  },
  common_unvalidate: {
    en: 'Edit Module',
    fr: 'Éditer le module',
  },
  common_delete_dialog_title: {
    en: 'Delete {item}',
    fr: 'Supprimer {item}',
  },
  common_delete_dialog_description: {
    en: 'Are you sure you want to delete {item}? This action cannot be undone.',
    fr: 'Êtes-vous sûr de vouloir supprimer {item} ? Cette action est irréversible.',
  },
  common_edit_dialog_title: {
    en: 'Edit {item}',
    fr: 'Éditer {item}',
  },
  common_delete: {
    en: 'Delete',
    fr: 'Supprimer',
  },
  common_cancel: {
    en: 'Cancel',
    fr: 'Annuler',
  },
  common_save: {
    en: 'Save',
    fr: 'Enregistrer',
  },
  common_view_only: {
    en: 'View Only',
    fr: 'Lecture seule',
  },
  header_documentation_link: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/',
  },
  header_backoffice_documentation_link: {
    en: 'https://epfl-enac.github.io/co2-calculator-back-office-doc/',
    fr: 'https://epfl-enac.github.io/co2-calculator-back-office-doc/',
  },
  header_dev_documentation_link: {
    en: 'https://epfl-enac.github.io/co2-calculator/',
    fr: 'https://epfl-enac.github.io/co2-calculator/',
  },
  header_user_documentation_link: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/',
  },
};
