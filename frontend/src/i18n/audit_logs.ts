// audit_ is the prefix for audit logs related translations
export default {
  // Filter options - Actions
  audit_filter_all_actions: {
    en: 'All Actions',
    fr: 'Toutes les actions',
  },
  audit_action_create: {
    en: 'CREATE',
    fr: 'CRÉER',
  },
  audit_action_read: {
    en: 'READ',
    fr: 'LIRE',
  },
  audit_action_update: {
    en: 'UPDATE',
    fr: 'METTRE À JOUR',
  },
  audit_action_delete: {
    en: 'DELETE',
    fr: 'SUPPRIMER',
  },
  audit_action_rollback: {
    en: 'ROLLBACK',
    fr: 'ANNULER',
  },
  audit_action_transfer: {
    en: 'TRANSFER',
    fr: 'TRANSFÉRER',
  },

  // Filter options - Entity Types
  audit_filter_all_entities: {
    en: 'All Entities',
    fr: 'Toutes les entités',
  },
  audit_entity_data_entry: {
    en: 'DataEntry',
    fr: 'Saisie de données',
  },
  audit_entity_data_ingestion_job: {
    en: 'DataIngestionJob',
    fr: "Tâche d'ingestion",
  },
  audit_entity_user: {
    en: 'User',
    fr: 'Utilisateur',
  },
  audit_entity_factor: {
    en: 'Factor',
    fr: 'Facteur',
  },
  audit_entity_data_entry_read: {
    en: 'DataEntryReadByCarbonReportModule',
    fr: 'Lecture par module de rapport',
  },
  audit_entity_emission_factor: {
    en: 'EmissionFactor',
    fr: "Facteur d'émission",
  },

  // Filter options - Modules
  audit_filter_all_modules: {
    en: 'All Modules',
    fr: 'Tous les modules',
  },
  audit_module_headcount: {
    en: 'Headcount',
    fr: 'Effectifs',
  },
  audit_module_professional_travel: {
    en: 'Professional Travel',
    fr: 'Déplacements professionnels',
  },
  audit_module_infrastructure: {
    en: 'Infrastructure',
    fr: 'Infrastructure',
  },
  audit_module_equipment_electric: {
    en: 'Equipment Electric Consumption',
    fr: 'Consommation électrique des équipements',
  },
  audit_module_purchase: {
    en: 'Purchase',
    fr: 'Achats',
  },
  audit_module_internal_services: {
    en: 'Internal Services',
    fr: 'Services internes',
  },
  audit_module_external_cloud: {
    en: 'External Cloud and AI',
    fr: 'Cloud et IA externes',
  },

  // Filter options - Date presets
  audit_date_all_time: {
    en: 'All Time',
    fr: 'Toute la période',
  },
  audit_date_today: {
    en: 'Today',
    fr: "Aujourd'hui",
  },
  audit_date_last_7_days: {
    en: 'Last 7 days',
    fr: '7 derniers jours',
  },
  audit_date_last_30_days: {
    en: 'Last 30 days',
    fr: '30 derniers jours',
  },
  audit_date_custom_range: {
    en: 'Custom range...',
    fr: 'Plage personnalisée...',
  },

  // Filter labels
  audit_label_handler_id: {
    en: 'Handler ID',
    fr: 'ID du gestionnaire',
  },
  audit_label_from: {
    en: 'From',
    fr: 'De',
  },
  audit_label_to: {
    en: 'To',
    fr: 'À',
  },
  audit_btn_apply: {
    en: 'Apply',
    fr: 'Appliquer',
  },

  // Table column headers
  audit_col_action: {
    en: 'Action',
    fr: 'Action',
  },
  audit_col_entity_type: {
    en: 'Entity Type',
    fr: "Type d'entité",
  },
  audit_col_entity_id: {
    en: 'Entity ID',
    fr: "ID d'entité",
  },
  audit_col_timestamp: {
    en: 'Timestamp',
    fr: 'Horodatage',
  },
  audit_col_user: {
    en: 'User',
    fr: 'Utilisateur',
  },
  audit_col_handler_id: {
    en: 'Handler ID',
    fr: 'ID du gestionnaire',
  },
  audit_col_summary: {
    en: 'Summary',
    fr: 'Résumé',
  },
  audit_col_actions: {
    en: 'Actions',
    fr: 'Actions',
  },

  // Table messages/labels
  audit_no_entries_found: {
    en: 'No audit entries found',
    fr: "Aucune entrée d'audit trouvée",
  },
  audit_adjust_filters: {
    en: 'Try adjusting your filters or search query.',
    fr: "Essayez d'ajuster vos filtres ou votre recherche.",
  },
  audit_user_unknown: {
    en: 'Unknown',
    fr: 'Inconnu',
  },
  audit_user_job_id: {
    en: 'JobId: {id}',
    fr: 'TâcheId: {id}',
  },

  // Action buttons
  audit_btn_view: {
    en: 'View',
    fr: 'Voir',
  },
  audit_btn_copy: {
    en: 'Copy',
    fr: 'Copier',
  },
  audit_btn_search: {
    en: 'Search',
    fr: 'Rechercher',
  },
  audit_btn_export_csv: {
    en: 'Export as CSV',
    fr: 'Exporter en CSV',
  },
  audit_btn_export_json: {
    en: 'Export as JSON',
    fr: 'Exporter en JSON',
  },
  audit_btn_close: {
    en: 'Close',
    fr: 'Fermer',
  },
  audit_btn_retry: {
    en: 'Retry',
    fr: 'Réessayer',
  },

  // Search bar
  audit_search_placeholder: {
    en: 'Search by user, entity, or reason...',
    fr: 'Rechercher par utilisateur, entité ou raison...',
  },

  // Pagination
  audit_page_showing: {
    en: 'Showing',
    fr: 'Affichage',
  },
  audit_page_of: {
    en: 'of',
    fr: 'sur',
  },
  audit_page_entries: {
    en: 'entries',
    fr: 'entrées',
  },
  audit_page_rows_per_page: {
    en: 'Rows per page:',
    fr: 'Lignes par page :',
  },

  // Stats cards
  audit_stat_total: {
    en: 'TOTAL ENTRIES',
    fr: 'TOTAL DES ENTRÉES',
  },
  audit_stat_creates: {
    en: 'CREATES',
    fr: 'CRÉATIONS',
  },
  audit_stat_updates: {
    en: 'UPDATES',
    fr: 'MISES À JOUR',
  },
  audit_stat_deletes: {
    en: 'DELETES',
    fr: 'SUPPRESSIONS',
  },

  // Detail drawer - Section titles
  audit_detail_metadata: {
    en: 'Metadata',
    fr: 'Métadonnées',
  },
  audit_detail_changes: {
    en: 'Changes',
    fr: 'Modifications',
  },
  audit_detail_snapshot: {
    en: 'Full Data Snapshot',
    fr: 'Instantané complet des données',
  },

  // Detail drawer - Metadata labels
  audit_detail_entity_type: {
    en: 'Entity Type',
    fr: "Type d'entité",
  },
  audit_detail_entity_id: {
    en: 'Entity ID',
    fr: "ID d'entité",
  },
  audit_detail_version: {
    en: 'Version',
    fr: 'Version',
  },
  audit_detail_user: {
    en: 'User',
    fr: 'Utilisateur',
  },
  audit_detail_handler_id: {
    en: 'Handler ID',
    fr: 'ID du gestionnaire',
  },
  audit_detail_ip_address: {
    en: 'IP Address',
    fr: 'Adresse IP',
  },
  audit_detail_route: {
    en: 'Route',
    fr: 'Route',
  },
  audit_detail_reason: {
    en: 'Reason',
    fr: 'Raison',
  },
  audit_detail_handled_ids: {
    en: 'Handled IDs',
    fr: 'IDs traités',
  },

  // Detail drawer - Diff labels
  audit_detail_before: {
    en: 'Before:',
    fr: 'Avant :',
  },
  audit_detail_after: {
    en: 'After:',
    fr: 'Après :',
  },
  audit_detail_added: {
    en: '+ Added',
    fr: '+ Ajouté',
  },
  audit_detail_removed: {
    en: '- Removed',
    fr: '- Supprimé',
  },

  // Detail drawer - Buttons
  audit_btn_copy_json: {
    en: 'Copy JSON',
    fr: 'Copier JSON',
  },

  // Notification messages
  audit_msg_load_failed: {
    en: 'Failed to load audit logs.',
    fr: "Échec du chargement des journaux d'audit.",
  },
  audit_msg_detail_load_failed: {
    en: 'Failed to load audit log detail',
    fr: "Échec du chargement des détails du journal d'audit",
  },
  audit_msg_copied: {
    en: 'Copied to clipboard',
    fr: 'Copié dans le presse-papiers',
  },
  audit_msg_exported: {
    en: 'Exported as {format}',
    fr: 'Exporté en {format}',
  },
  audit_msg_export_failed: {
    en: 'Export failed',
    fr: "Échec de l'exportation",
  },
} as const;
