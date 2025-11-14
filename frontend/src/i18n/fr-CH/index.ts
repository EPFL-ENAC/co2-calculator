import { MODULES } from 'src/constant/modules';
import { ROLES } from 'src/constant/roles';

// This is just an example,
// so you can safely delete all default props below

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
  'backoffice-documentation-editing': 'Édition de la documentation',
  'backoffice-documentation': 'Documentation Backoffice',
  'system-documentation': 'Documentation système',
  results_btn: 'Voir les résultats',
  logout: 'Se déconnecter',
  workspace_setup_title: "Configuration de l'espace de travail",
  workspace_setup_description:
    "Veuillez configurer votre espace de travail avant d'utiliser le calculateur de CO₂.",
  workspace_setup_unit_title: 'Sélectionnez votre laboratoire',
  workspace_setup_unit_description:
    'Vous avez accès à plusieurs laboratoires. Veuillez sélectionner celui sur lequel vous souhaitez travailler :',
  workspace_setup_unit_counter: 'Vos laboratoires ({count})',
  workspace_setup_unit_role: 'Votre rôle :',
  [ROLES.StandardUser]: 'Utilisateur standard',
  [ROLES.PrincipalUser]: 'Utilisateur principal',
  [ROLES.SecondaryUser]: 'Utilisateur secondaire',
  [ROLES.BackOfficeAdmin]: 'Administrateur Backoffice',
  [ROLES.BackOfficeStandard]: 'Utilisateur standard Backoffice',
  [ROLES.System]: 'Gestionnaire système',
  workspace_setup_year_title: "Sélectionnez l'année de calcul",
  workspace_setup_year_description:
    "Veuillez sélectionner l'année pour laquelle vous souhaitez effectuer les calculs de CO₂ :",
  workspace_setup_year_counter: 'Années enregistrées ({count})',
  workspace_setup_confirm_lab: 'Laboratoire sélectionné',
  workspace_setup_confirm_year: 'Année sélectionnée',
  workspace_setup_confirm_selection: 'Continuer vers le calculateur',
  workspace_setup_restart: 'Recommencer',
  workspace_setup_unit_manager: "Responsable d'unité",
  workspace_setup_unit_affiliation: 'Affiliation',
  workspace_setup_unit_progress: "Progression de l'année dernière",
};
