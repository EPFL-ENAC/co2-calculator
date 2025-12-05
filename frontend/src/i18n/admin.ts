import { SYSTEM_NAV } from 'src/constant/navigation';

export default {
  [SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.routeName]: {
    en: 'User Management',
    fr: 'Gestion des utilisateurs',
  },
  [SYSTEM_NAV.SYSTEM_USER_MANAGEMENT.description]: {
    en: 'Manage user accounts, assign roles and permissions, monitor user activity, and control access to the CO₂ calculator.',
    fr: "Gérer les comptes utilisateurs, assigner des rôles et des permissions, surveiller l'activité des utilisateurs, et contrôler l'accès au calculateur CO₂.",
  },
  [SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.routeName]: {
    en: 'Module Management',
    fr: 'Gestion des modules',
  },
  [SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.description]: {
    en: 'Enable or disable calculation modules system-wide, controlling which data collection features are available to all laboratories.',
    fr: 'Activer ou désactiver les modules de calcul systématiquement, contrôlant quelles fonctionnalités de collecte de données sont disponibles pour tous les laboratoires.',
  },
  [SYSTEM_NAV.SYSTEM_LOGS.routeName]: {
    en: 'Logs',
    fr: 'Logs',
  },
  [SYSTEM_NAV.SYSTEM_LOGS.description]: {
    en: 'View, search, and export application logs and user activity history for security auditing and troubleshooting.',
    fr: "Voir, rechercher et exporter les logs de l'application et l'historique d'activité des utilisateurs pour la sécurité et le dépannage.",
  },
  module_management_active: {
    en: 'Active',
    fr: 'Actif',
  },
  module_management_consequences_title: {
    en: 'Consequences of disabling a module:',
    fr: 'Conséquences de la désactivation d’un module :',
  },
  module_management_consequence_no_access: {
    en: 'No laboratory will have access to this module(s)',
    fr: 'Aucun laboratoire n’aura accès à ce(s) module(s)',
  },
  module_management_consequence_not_on_home: {
    en: 'The module will not appear on the Home page',
    fr: 'Le module n’apparaîtra pas sur la page d’accueil',
  },
  module_management_consequence_not_in_results: {
    en: 'The data category entered in this module will not appear in the results visualization module',
    fr: 'La catégorie de données saisie dans ce module n’apparaîtra pas dans le module de visualisation des résultats',
  },
  module_management_consequence_important: {
    en: 'Important: References to these modules in documentation pages and explanatory texts must be manually removed via the Business Manager (Full) interface',
    fr: 'Important : Les références à ces modules dans les pages de documentation et les textes explicatifs doivent être supprimées manuellement via l’interface Business Manager (Complet)',
  },
  module_management_save_button: {
    en: 'Save',
    fr: 'Enregistrer',
  },
  user_management_page_description_system: {
    en: 'User management at EPFL is handled via Accred.',
    fr: "La gestion des utilisateurs à l'EPFL est gérée via Accred.",
  },
  user_management_page_button_label_system: {
    en: 'Go to User management system (Accred)',
    fr: 'Accéder au système de gestion des utilisateurs (Accred)',
  },
  user_management_page_button_documentation_label_system: {
    en: 'Go to User management system documentation',
    fr: 'Documentation de la gestion des utilisateurs',
  },
} as const;
