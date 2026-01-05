import { ROLES } from 'src/constant/roles';
import { MODULES } from 'src/constant/modules';

export default {
  logo_alt: {
    en: 'Logo EPFL',
    fr: 'EPFL Logo',
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
    fr: 'Module Results',
  },
  results: {
    en: 'Results',
    fr: 'Results',
  },
  simulations: {
    en: 'Simulations',
    fr: 'Simulations',
  },
  'simulation-add': {
    en: 'Add Simulation',
    fr: 'Add Simulation',
  },
  'simulation-edit': {
    en: 'Edit Simulation',
    fr: 'Edit Simulation',
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
    en: 'Standard User',
    fr: 'Standard User',
  },
  [ROLES.PrincipalUser]: {
    en: 'Principal User',
    fr: 'Principal User',
  },
  [ROLES.SecondaryUser]: {
    en: 'Secondary User',
    fr: 'Secondary User',
  },
  [ROLES.BackOfficeAdmin]: {
    en: 'Backoffice Admin',
    fr: 'Backoffice Administrator',
  },
  [ROLES.BackOfficeStandard]: {
    en: 'Backoffice Standard User',
    fr: 'Backoffice Standard',
  },
  [ROLES.System]: {
    en: 'System Manager',
    fr: 'Gestionnaire système',
  },
  info_with_link: {
    en: '<span>For more information, visit <a href="{url}" target="_blank">{linkText}</a>.</span>',
    fr: '<span>For more information, visit <a href="{url}" target="_blank">{linkText}</a>.</span>',
  },
  documentation_link: {
    en: 'Documentation and Resources',
    fr: 'Documentation and Resources',
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
      return 'kg CO₂-eq';
    },
    fr: ({ named }) => {
      if (named('type') === MODULES.MyLab) {
        return 'ETP';
      }
      return 'kg CO₂-eq';
    },
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
  header_documentation_link: {
    en: 'https://epfl-enac.github.io/co2-calculator/',
    fr: 'https://epfl-enac.github.io/co2-calculator/',
  },
};
