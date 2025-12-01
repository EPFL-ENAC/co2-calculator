import { ROLES } from 'src/constant/roles';

export default {
  logo_alt: {
    en: 'Logo EPFL',
    fr: 'EPFL Logo',
  },
  login_title: {
    en: 'CO₂ Calculator',
    fr: 'Calculateur de CO₂',
  },
  login_button_submit: {
    en: 'Login',
    fr: 'Log in',
  },
  login_button_loading: {
    en: 'Connecting...',
    fr: 'Logging in...',
  },
  login_test_role_label: {
    en: 'Test Role',
    fr: 'Rôle de test',
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
  results_btn: {
    en: 'View Results',
    fr: 'Voir les résultats',
  },
  workspace_change_btn: {
    en: 'Change',
    fr: 'Changer',
  },
  logout: {
    en: 'Logout',
    fr: 'Se déconnecter',
  },
  workspace_setup_title: {
    en: 'Welcome to the CO₂ calculator',
    fr: 'Bienvenue dans le calculateur CO₂',
  },
  workspace_setup_description: {
    en: "Assess your unit's carbon footprint in line with the Greenhouse Gas (GHG) Protocol — the international standard for greenhouse gas accounting.\n\nFollow the steps below to get started: select your unit, choose a calculation year, and proceed to measure your CO₂ emissions.",
    fr: 'Please set up your workspace before using the CO₂ calculator.',
  },
  workspace_setup_unit_title: {
    en: 'Select your lab',
    fr: 'Select Your Laboratory',
  },
  workspace_setup_unit_description: {
    en: 'Choose the unit you want to assess for its carbon footprint.',
    fr: 'You have access to several laboratories. Please select the one you wish to work on:',
  },
  workspace_setup_unit_counter: {
    en: 'Your units({count})',
    fr: 'Your Laboratories ({count})',
  },
  workspace_setup_unit_role: {
    en: 'Your role:',
    fr: 'Your Role:',
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
  workspace_setup_year_title: {
    en: 'Assessment years',
    fr: 'Années d’évaluation',
  },
  workspace_setup_year_description: {
    en: 'Choose which year to work on. ',
    fr: 'Choisissez l’année sur laquelle vous souhaitez travailler.',
  },
  workspace_setup_year_counter: {
    en: 'Recorded Years ({count})',
    fr: 'Années enregistrées ({count})',
  },
  workspace_setup_year_table_header_year: {
    en: 'Year',
    fr: 'Année',
  },
  workspace_setup_year_table_header_progress: {
    en: 'Progress',
    fr: 'Progression',
  },
  workspace_setup_year_table_header_comparison: {
    en: 'Comparison',
    fr: 'Comparaison',
  },
  workspace_setup_year_table_header_kgco2: {
    en: 'kg CO₂-eq',
    fr: 'kg CO₂-éq',
  },
  workspace_setup_unit_error: {
    en: 'Failed to load units.',
    fr: 'Échec du chargement des unités.',
  },
  workspace_setup_unit_no_units: {
    en: 'No units available. Please contact your administrator.',
    fr: 'Aucune unité disponible. Veuillez contacter votre administrateur.',
  },
  workspace_setup_confirm_lab: {
    en: 'Selected Lab',
    fr: 'Laboratoire sélectionné',
  },
  workspace_setup_year_error: {
    en: 'Failed to load years.',
    fr: 'Échec du chargement des années.',
  },
  workspace_setup_confirm_year: {
    en: 'Selected Year',
    fr: 'Année sélectionnée',
  },
  workspace_setup_confirm_selection: {
    en: 'Continue to calculator',
    fr: 'Continuer vers le calculateur',
  },
  workspace_setup_restart: {
    en: 'Start Over',
    fr: 'Recommencer',
  },
  workspace_setup_unit_manager: {
    en: 'Unit Manager',
    fr: "Responsable d'unité",
  },
  workspace_setup_unit_affiliation: {
    en: 'Affiliation',
    fr: 'Affiliation',
  },
  workspace_setup_unit_progress: {
    en: 'Progress from last year',
    fr: "Progression de l'année dernière",
  },
  home_title: {
    en: 'Welcome to the CO2 Calculator',
    fr: 'Bienvenue dans le Calculateur de CO2',
  },
  home_intro_1: {
    en: "The Calculator CO₂ allows you to assess your laboratory's carbon footprint following the Greenhouse Gas (GHG) Protocol, the international standard for calculating greenhouse gas emissions.",
    fr: "Le Calculateur CO₂ vous permet d'évaluer l'empreinte carbone de votre laboratoire selon le Protocole des gaz à effet de serre (GES), la norme internationale pour le calcul des émissions de gaz à effet de serre.",
  },
  home_intro_2: {
    en: "Complete the various data entry modules to obtain a comprehensive estimate of your laboratory's CO₂ equivalent emissions. Data can be entered manually or imported via CSV file.",
    fr: 'Complétez les différents modules de saisie de données pour obtenir une estimation complète des émissions équivalentes CO₂ de votre laboratoire. Les données peuvent être saisies manuellement ou importées via un fichier CSV.',
  },
  home_intro_3: {
    en: 'As a Principal User, you have full access to all calculator functionalities. You can delegate access to other team members by granting them Principal User or Standard User roles.',
    fr: "En tant qu'Utilisateur principal, vous avez un accès complet à toutes les fonctionnalités du calculateur. Vous pouvez déléguer l'accès à d'autres membres de l'équipe en leur attribuant les rôles d'Utilisateur principal ou d'Utilisateur standard.",
  },
  home_intro_4: {
    en: 'You can complete all data entry modules (My Laboratory, Professional Travel, Infrastructure, Equipment Electrical Consumption, Purchases, Internal Services, External Cloud Impact), view and analyze your results, simulate research projects, and export your data.',
    fr: 'Vous pouvez compléter tous les modules de saisie de données (Mon laboratoire, Déplacements professionnels, Infrastructure, Consommation électrique des équipements, Achats, Services internes, Impact du cloud externe), consulter et analyser vos résultats, simuler des projets de recherche et exporter vos données.',
  },
  home_intro_5: {
    en: "For more information on the methodology and EPFL's Climate and Sustainability Strategy, visit our {documentationLink} page. If you need assistance, please visit our {contactLink} page.",
    fr: "Pour plus d'informations sur la méthodologie et la stratégie Climat et Durabilité de l'EPFL, visitez notre page {documentationLink}. Si vous avez besoin d'aide, veuillez consulter notre page {contactLink}.",
  },
  home_intro_6: {
    en: 'Click the Start button below to begin completing the modules sequentially, or access individual modules directly in the section below. Once validated, your results will be available for visualization with detailed breakdowns and multi-year comparisons.',
    fr: 'Cliquez sur le bouton Démarrer ci-dessous pour commencer à compléter les modules séquentiellement, ou accédez directement aux modules individuels dans la section ci-dessous. Une fois validés, vos résultats seront disponibles pour visualisation avec des analyses détaillées et des comparaisons pluriannuelles.',
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
  home_start_button: {
    en: 'Start',
    fr: 'Start',
  },
  home_in_progress: {
    en: 'In Progress',
    fr: 'En Cours',
  },
  home_results_title: {
    en: 'Results Visualization',
    fr: 'Visualisation Voire',
  },
  home_results_subtitle: {
    en: 'Annual CO2 Assessment 2024',
    fr: 'Bilan CO2 Annuel 2024',
  },
  home_results_btn: {
    en: 'View Full Results',
    fr: 'Voir les Résultats Complets',
  },
  home_simulations_title: {
    en: 'Research Project Simulation',
    fr: 'Simulation de Projet de Recherche',
  },
  home_simulations_subtitle: {
    en: 'Estimate project-specific carbon footprint ',
    fr: "Estimer l'empreinte carbone spécifique au projet",
  },
  home_simulations_btn: {
    en: 'View Simulations',
    fr: 'Voir les Simulations',
  },
  home_edit_btn: {
    en: 'Edit',
    fr: 'Editer',
  },
  results_units: {
    en: 'kg CO₂-eq',
    fr: 'kg CO₂-éq',
  },
  home_simulations_units: {
    en: 'Simulations',
    fr: 'Simulations',
  },
  module_total_result_title: {
    en: 'Total Lab Carbon Footprint',
    fr: '',
  },
};
