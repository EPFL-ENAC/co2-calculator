import { MODULES } from 'src/constant/modules';
import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/sidebarNavigation';

export default {
  logo_alt: 'Logo EPFL',
  login_title: 'CO₂ Calculator',
  login_button_submit: 'Login',
  login_button_loading: 'Connecting...',
  calculator_title: 'CO₂ Calculator',
  home: 'Home',
  [MODULES.MyLab]: 'My Lab',
  [MODULES.ProfessionalTravel]: 'Professional Travel',
  [MODULES.Infrastructure]: 'Infrastructure',
  [MODULES.EquipmentElectricConsumption]: 'Equipment Electric Consumption',
  [MODULES.Purchase]: 'Purchases',
  [MODULES.InternalServices]: 'Internal Services',
  [MODULES.ExternalCloud]: 'External Cloud',
  module: 'Module',
  'module-results': 'Module Results',
  results: 'Results',
  simulations: 'Simulations',
  'simulation-add': 'Add Simulation',
  'simulation-edit': 'Edit Simulation',
  documentation: 'Documentation',
  [BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.routeName]: 'User Management',
  [BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName]: 'Data Management',
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.routeName]:
    'Documentation Editing',
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName]: 'Reporting',
  [SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.routeName]: 'User Management',
  [SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.routeName]: 'Module Management',
  [SYSTEM_NAV.SYSTEM_LOGS.routeName]: 'Logs',

  results_btn: 'View Results',
  logout: 'Logout',
};
