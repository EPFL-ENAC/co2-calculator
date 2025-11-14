import { MODULES } from 'src/constant/modules';
import { ROLES } from 'src/constant/roles';

// This is just an example,
// so you can safely delete all default props below

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
  'backoffice-documentation-editing': 'Documentation Editing',
  'backoffice-documentation': 'Backoffice Documentation',
  'system-documentation': 'System Documentation',
  results_btn: 'View Results',
  logout: 'Logout',
  workspace_setup_title: 'Workspace Setup',
  workspace_setup_description:
    'Please configure your workspace before using the CO₂ calculator.',
  workspace_setup_unit_title: 'Select your lab',
  workspace_setup_unit_description:
    'You have access to multiple laboratories. Please select which one you want to work on:',
  workspace_setup_unit_counter: 'Your Labs ({count})',
  workspace_setup_unit_role: 'Your role:',
  [ROLES.StandardUser]: 'Standard User',
  [ROLES.PrincipalUser]: 'Principal User',
  [ROLES.SecondaryUser]: 'Secondary User',
  [ROLES.BackOfficeAdmin]: 'Backoffice Admin',
  [ROLES.BackOfficeStandard]: 'Backoffice Standard User',
  [ROLES.System]: 'System Manager',
  workspace_setup_year_title: 'Select the calculation year',
  workspace_setup_year_description:
    'Please select the year for which you want to perform CO₂ calculations:',
  workspace_setup_year_counter: 'Recorded Years ({count})',
  workspace_setup_confirm_lab: 'Selected Lab',
  workspace_setup_confirm_year: 'Selected Year',
  workspace_setup_confirm_selection: 'Continue to calculator',
  workspace_setup_restart: 'Start Over',

  workspace_setup_unit_manager: 'Unit Manager',
  workspace_setup_unit_affiliation: 'Affiliation',
  workspace_setup_unit_progress: 'Progress from last year',
};
