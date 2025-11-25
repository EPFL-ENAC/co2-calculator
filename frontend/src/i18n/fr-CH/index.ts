import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';
import { ROLES } from 'src/constant/roles';
import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/navigation';

export default {
  logo_alt: 'EPFL Logo',
  login_title: 'CO₂ Calculator',
  login_button_submit: 'Log in',
  login_button_loading: 'Logging in...',
  login_test_role_label: 'Rôle de test',
  calculator_title: 'CO₂ Calculator',
  home: 'Home',
  [MODULES.MyLab]: 'My Laboratory',
  [MODULES_DESCRIPTIONS.MyLab]:
    'Enter staff and FTEs to establish your laboratory profile',
  [MODULES.ProfessionalTravel]: 'Professional Travel',
  [MODULES_DESCRIPTIONS.ProfessionalTravel]:
    'Record team trips by plane and train with automatic CO₂ calculations',
  [MODULES.Infrastructure]: 'Infrastructure',
  [MODULES_DESCRIPTIONS.Infrastructure]:
    "Define your laboratory's physical footprint in EPFL buildings and spaces.",
  [MODULES.EquipmentElectricConsumption]: 'Equipment Electricity Consumption',
  [MODULES_DESCRIPTIONS.EquipmentElectricConsumption]:
    'List laboratory equipment with their power to calculate CO₂ related to electricity',
  [MODULES.Purchase]: 'Purchases',
  [MODULES_DESCRIPTIONS.Purchase]:
    'Enter annual purchases to assess the supply chain footprint',
  [MODULES.InternalServices]: 'Internal Services',
  [MODULES_DESCRIPTIONS.InternalServices]:
    'Track the use of EPFL internal platforms and services.',
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
  [BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.routeName]:
    'Gestion des utilisateurs',
  [BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT.description]:
    'backoffice-user-management-description',
  [BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName]: 'Gestion des données',
  [BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.description]:
    'backoffice-data-management-description',
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.routeName]:
    'Édition de la documentation',
  [BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING.description]:
    'backoffice-documentation-editing-description',
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.routeName]: 'Rapports',
  [BACKOFFICE_NAV.BACKOFFICE_REPORTING.description]:
    'backoffice-reporting-description',
  [SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.routeName]: 'Gestion des utilisateurs',
  [SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.description]:
    "Gérer les comptes utilisateurs, assigner des rôles et des permissions, surveiller l'activité des utilisateurs, et contrôler l'accès au calculateur CO₂.",
  [SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.routeName]: 'Gestion des modules',
  [SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.description]:
    'Activer ou désactiver les modules de calcul systématiquement, contrôlant quelles fonctionnalités de collecte de données sont disponibles pour tous les laboratoires.',
  [SYSTEM_NAV.SYSTEM_LOGS.routeName]: 'Logs',
  [SYSTEM_NAV.SYSTEM_LOGS.description]:
    "Voir, rechercher et exporter les logs de l'application et l'historique d'activité des utilisateurs pour la sécurité et le dépannage.",

  results_btn: 'Voir les résultats',
  workspace_change_btn: 'Changer',
  logout: 'Se déconnecter',
  workspace_setup_title: 'Bienvenue dans le calculateur CO₂',
  workspace_setup_description:
    'Please set up your workspace before using the CO₂ calculator.',
  workspace_setup_unit_title: 'Select Your Laboratory',
  workspace_setup_unit_description:
    'You have access to several laboratories. Please select the one you wish to work on:',
  workspace_setup_unit_counter: 'Your Laboratories ({count})',
  workspace_setup_unit_role: 'Your Role:',
  [ROLES.StandardUser]: 'Standard User',
  [ROLES.PrincipalUser]: 'Principal User',
  [ROLES.SecondaryUser]: 'Secondary User',
  [ROLES.BackOfficeAdmin]: 'Backoffice Administrator',
  [ROLES.BackOfficeStandard]: 'Backoffice Standard',
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
  workspace_setup_unit_affiliation: 'Affiliation',
  workspace_setup_unit_progress: "Progression de l'année dernière",
  home_title: 'Bienvenue dans le Calculateur de CO2',
  home_intro_1:
    "Le Calculateur CO₂ vous permet d'évaluer l'empreinte carbone de votre laboratoire selon le Protocole des gaz à effet de serre (GES), la norme internationale pour le calcul des émissions de gaz à effet de serre.",
  home_intro_2:
    'Complétez les différents modules de saisie de données pour obtenir une estimation complète des émissions équivalentes CO₂ de votre laboratoire. Les données peuvent être saisies manuellement ou importées via un fichier CSV.',
  home_intro_3:
    "En tant qu'Utilisateur principal, vous avez un accès complet à toutes les fonctionnalités du calculateur. Vous pouvez déléguer l'accès à d'autres membres de l'équipe en leur attribuant les rôles d'Utilisateur principal ou d'Utilisateur standard.",
  home_intro_4:
    'Vous pouvez compléter tous les modules de saisie de données (Mon laboratoire, Déplacements professionnels, Infrastructure, Consommation électrique des équipements, Achats, Services internes, Impact du cloud externe), consulter et analyser vos résultats, simuler des projets de recherche et exporter vos données.',
  home_intro_5:
    "Pour plus d'informations sur la méthodologie et la stratégie Climat et Durabilité de l'EPFL, visitez notre page {documentationLink}. Si vous avez besoin d'aide, veuillez consulter notre page {contactLink}.",
  home_intro_6:
    'Cliquez sur le bouton Démarrer ci-dessous pour commencer à compléter les modules séquentiellement, ou accédez directement aux modules individuels dans la section ci-dessous. Une fois validés, vos résultats seront disponibles pour visualisation avec des analyses détaillées et des comparaisons pluriannuelles.',
  info_with_link:
    '<span>For more information, visit <a href="{url}" target="_blank">{linkText}</a>.</span>',
  documentation_link: 'Documentation and Resources',
  contact: 'Contact',
  home_start_button: 'Start',
  home_in_progress: 'En Cours',
  home_results_title: 'Visualisation Voire',
  home_results_subtitle: 'Bilan CO2 Annuel 2024',
  home_results_btn: 'Voir les Résultats Complets',
  home_simulations_title: 'Simulation de Projet de Recherche',
  home_simulations_subtitle: "Estimer l'empreinte carbone spécifique au projet",
  home_simulations_btn: 'Voir les Simulations',
  home_edit_btn: 'Editer',
  home_results_units: 'kg CO₂-éq',
  home_simulations_units: 'Simulations',
  module_management_active: 'Actif',
  module_management_consequences_title:
    'Conséquences de la désactivation d’un module :',
  module_management_consequence_no_access:
    'Aucun laboratoire n’aura accès à ce(s) module(s)',
  module_management_consequence_not_on_home:
    'Le module n’apparaîtra pas sur la page d’accueil',
  module_management_consequence_not_in_results:
    'La catégorie de données saisie dans ce module n’apparaîtra pas dans le module de visualisation des résultats',
  module_management_consequence_important:
    'Important : Les références à ces modules dans les pages de documentation et les textes explicatifs doivent être supprimées manuellement via l’interface Business Manager (Complet)',
  module_management_save_button: 'Enregistrer',
  threshold_fixed_title: 'Seuil Fixe',
  threshold_fixed_description:
    'Définis un seuil fixe. Toute valeur supérieure sera signalée en rouge.',
  threshold_fixed_value: 'Valeur fixe (kg CO₂-éq)',
  threshold_fixed_summary: 'Seuil fixe de {value} kg CO₂-éq',
  threshold_median_title: 'Seuil basé sur la médiane',
  threshold_median_description:
    'Signale automatiquement les émissions supérieures à la valeur médiane. S’ajuste en fonction de toutes les données des laboratoires.',
  threshold_median_info: 'Automatique',
  threshold_median_summary: 'Seuil basé sur la médiane',
  threshold_top_title: 'Seuil des valeurs les plus élevées',
  threshold_top_description:
    'Signale les émissions les plus élevées. Entrez le nombre de valeurs les plus élevées.',
  threshold_top_value: 'Nombre de valeurs les plus élevées',
  threshold_top_summary: '{value} valeurs les plus élevées',
};
