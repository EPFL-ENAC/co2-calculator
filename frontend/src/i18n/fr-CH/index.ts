import { MODULES } from 'src/constant/modules';
import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/sidebarNavigation';

export default {
  logo_alt: 'Logo EPFL',
  login_title: 'Calculateur CO₂',
  login_button_submit: 'Se connecter',
  login_button_loading: 'Connexion en cours...',
  calculator_title: 'Calculateur CO₂',
  home: 'Accueil',
  [MODULES.MyLab]: 'Mon laboratoire',
  [MODULES.ProfessionalTravel]: 'Voyages professionnels',
  [MODULES.Infrastructure]: 'Infrastructure',
  [MODULES.EquipmentElectricConsumption]:
    'Consommation électrique des équipements',
  [MODULES.Purchase]: 'Achats',
  [MODULES.InternalServices]: 'Services internes',
  [MODULES.ExternalCloud]: 'Cloud externe',
  module: 'Module',
  'module-results': 'Résultats du module',
  results: 'Résultats',
  simulations: 'Simulations',
  'simulation-add': 'Ajouter une simulation',
  'simulation-edit': 'Modifier la simulation',
  documentation: 'Documentation',
  [BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.routeName]:
    'Gestion des utilisateurs',
  [BACKOFFICE_NAV.BACKOFFICE_MODULE_MANAGEMENT.routeName]:
    'Gestion des modules',
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.routeName]:
    'Édition de la documentation',
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName]: 'Rapports',
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION.routeName]:
    'Documentation Backoffice',
  [SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.routeName]: 'Gestion des utilisateurs',
  [SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.routeName]: 'Gestion des modules',
  [SYSTEM_NAV.SYSTEM_LOGS.routeName]: 'Journaux',
  [SYSTEM_NAV.SYSTEM_DOCUMENTATION.routeName]: 'Documentation système',

  results_btn: 'Voir les résultats',
  workspace_change_btn: 'Changer',
  logout: 'Se déconnecter',
  workspace_setup_title: 'Bienvenue dans le calculateur CO₂',
  workspace_setup_description:
    'Évaluez l’empreinte carbone de votre unité selon le Greenhouse Gas (GHG) Protocol — la norme internationale de référence pour le calcul des émissions de gaz à effet de serre.\n\nSuivez les étapes ci-dessous pour commencer : sélectionnez votre unité, choisissez une année de calcul, puis lancez la mesure de vos émissions de CO₂.',
  workspace_setup_unit_title: 'Sélectionnez votre laboratoire',
  workspace_setup_unit_description:
    'Choisissez l’unité que vous souhaitez évaluer pour son empreinte carbone.',
  workspace_setup_unit_counter: 'Vos unités ({count})',
  workspace_setup_unit_role: 'Votre rôle :',
  [ROLES.StandardUser]: 'Utilisateur standard',
  [ROLES.PrincipalUser]: 'Utilisateur principal',
  [ROLES.SecondaryUser]: 'Utilisateur secondaire',
  [ROLES.BackOfficeAdmin]: 'Administrateur Backoffice',
  [ROLES.BackOfficeStandard]: 'Utilisateur standard Backoffice',
  [ROLES.System]: 'Gestionnaire système',
  workspace_setup_year_title: 'Années d’évaluation',
  workspace_setup_year_description:
    'Choisissez l’année sur laquelle vous souhaitez travailler.',
  workspace_setup_year_counter: 'Années enregistrées ({count})',
  workspace_setup_year_table_header_year: 'Année',
  workspace_setup_year_table_header_progress: 'Progression',
  workspace_setup_year_table_header_comparison: 'Comparaison',
  workspace_setup_year_table_header_kgco2: 'kg CO₂-éq',
  workspace_setup_unit_error: 'Échec du chargement des unités.',
  workspace_setup_unit_no_units:
    'Aucune unité disponible. Veuillez contacter votre administrateur.',
  workspace_setup_confirm_lab: 'Laboratoire sélectionné',
  workspace_setup_year_error: 'Échec du chargement des années.',
  workspace_setup_confirm_year: 'Année sélectionnée',
  workspace_setup_confirm_selection: 'Continuer vers le calculateur',
  workspace_setup_restart: 'Recommencer',
  workspace_setup_unit_manager: "Responsable d'unité",
  workspace_setup_unit_affiliation: 'Affiliations',
  workspace_setup_unit_progress: ' Progrès (bilan {year})',
};
