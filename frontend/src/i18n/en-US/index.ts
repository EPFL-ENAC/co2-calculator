import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/sidebarNavigation';
import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';
import { ROLES } from 'src/constant/roles';

export default {
  logo_alt: 'Logo EPFL',
  login_title: 'CO₂ Calculator',
  login_button_submit: 'Login',
  login_button_loading: 'Connecting...',
  calculator_title: 'CO₂ Calculator',

  home: 'Home',
  [MODULES.MyLab]: 'My Lab',
  [MODULES_DESCRIPTIONS.MyLab]:
    'Enter personnel headcount and FTE values to establish your lab profile',
  [MODULES.ProfessionalTravel]: 'Professional Travel',
  [MODULES_DESCRIPTIONS.ProfessionalTravel]:
    'Record team travel by plane and train with automatic CO₂ calculations',
  [MODULES.Infrastructure]: 'Infrastructure',
  [MODULES_DESCRIPTIONS.Infrastructure]:
    "Define your lab's physical footprint across EPFL buildings and spaces.",
  [MODULES.EquipmentElectricConsumption]: 'Equipment Electric Con...',
  [MODULES_DESCRIPTIONS.EquipmentElectricConsumption]:
    'List lab equipment with wattage to calculate electricity-related CO₂',
  [MODULES.Purchase]: 'Purchases',
  [MODULES_DESCRIPTIONS.Purchase]:
    'Input annual purchases to assess supply chain emissions footprint',
  [MODULES.InternalServices]: 'Internal Services',
  [MODULES_DESCRIPTIONS.InternalServices]:
    'Track usage of EPFL internal platforms and services (e.g., microscopy center, computing).',
  [MODULES.ExternalCloud]: 'External Cloud',
  [MODULES_DESCRIPTIONS.ExternalCloud]:
    'Measure cloud computing emissions from external service providers.',
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
  workspace_change_btn: 'Change',
  logout: 'Logout',
  workspace_setup_title: 'Welcome to the CO₂ calculator',
  workspace_setup_description:
    "Assess your unit's carbon footprint in line with the Greenhouse Gas (GHG) Protocol — the international standard for greenhouse gas accounting.\n\nFollow the steps below to get started: select your unit, choose a calculation year, and proceed to measure your CO₂ emissions.",
  workspace_setup_unit_title: 'Select your lab',
  workspace_setup_unit_description:
    'Choose the unit you want to assess for its carbon footprint.',
  workspace_setup_unit_counter: 'Your units({count})',
  workspace_setup_unit_role: 'Your role:',
  [ROLES.StandardUser]: 'Standard User',
  [ROLES.PrincipalUser]: 'Principal User',
  [ROLES.SecondaryUser]: 'Secondary User',
  [ROLES.BackOfficeAdmin]: 'Backoffice Admin',
  [ROLES.BackOfficeStandard]: 'Backoffice Standard User',
  [ROLES.System]: 'System Manager',
  workspace_setup_year_title: 'Assessment years',
  workspace_setup_year_description: 'Choose which year to work on. ',
  workspace_setup_year_counter: 'Recorded Years ({count})',
  workspace_setup_year_table_header_year: 'Year',
  workspace_setup_year_table_header_progress: 'Progress',
  workspace_setup_year_table_header_comparison: 'Comparison',
  workspace_setup_year_table_header_kgco2: 'kg CO₂-eq',
  workspace_setup_unit_error: 'Failed to load units.',
  workspace_setup_unit_no_units:
    'No units available. Please contact your administrator.',
  workspace_setup_confirm_lab: 'Selected Lab',
  workspace_setup_year_error: 'Failed to load years.',
  workspace_setup_confirm_year: 'Selected Year',
  workspace_setup_confirm_selection: 'Continue to calculator',
  workspace_setup_restart: 'Start Over',
  workspace_setup_unit_manager: 'Unit Manager',
  workspace_setup_unit_affiliation: 'Affiliation',
  workspace_setup_unit_progress: 'Progress from last year',
  home_title: 'Welcome to the CO2 Calculator',
  home_intro_1:
    "The Calculator CO₂ allows you to assess your laboratory's carbon footprint following the Greenhouse Gas (GHG) Protocol, the international standard for calculating greenhouse gas emissions.",
  home_intro_2:
    "Complete the various data entry modules to obtain a comprehensive estimate of your laboratory's CO₂ equivalent emissions. Data can be entered manually or imported via CSV file.",
  home_intro_3:
    'As a Principal User, you have full access to all calculator functionalities. You can delegate access to other team members by granting them Principal User or Standard User roles.',
  home_intro_4:
    'You can complete all data entry modules (My Laboratory, Professional Travel, Infrastructure, Equipment Electrical Consumption, Purchases, Internal Services, External Cloud Impact), view and analyze your results, simulate research projects, and export your data.',
  home_intro_5:
    "For more information on the methodology and EPFL's Climate and Sustainability Strategy, visit our {documentationLink} page. If you need assistance, please visit our {contactLink} page.",
  home_intro_6:
    'Click the Start button below to begin completing the modules sequentially, or access individual modules directly in the section below. Once validated, your results will be available for visualization with detailed breakdowns and multi-year comparisons.',
  info_with_link:
    '<span>For more information, visit <a href="{url}" target="_blank">{linkText}</a>.</span>',
  documentation_link: 'Documentation and Resources',
  contact: 'Contact',
  home_start_button: 'Start',
  home_in_progress: 'In Progress',
  home_results_title: 'Results Visualization',
  home_results_subtitle: 'Annual CO2 Assessment 2024',
  home_results_btn: 'View Full Results',
  home_simulations_title: 'Research Project Simulation',
  home_simulations_subtitle: 'Estimate project-specific carbon footprint ',
  home_simulations_btn: 'View Simulations',
  home_edit_btn: 'Edit',
  home_results_units: 'kg CO₂-eq',
  home_simulations_units: 'Simulations',
};
