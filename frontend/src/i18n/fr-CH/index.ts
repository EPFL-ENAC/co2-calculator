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
  logout: 'Se déconnecter',
};
