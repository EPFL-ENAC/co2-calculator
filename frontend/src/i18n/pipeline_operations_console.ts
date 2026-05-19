// Issue #1234 — pipeline operations console (back-office).
// Auto-registered by the eager glob in src/i18n/index.ts.

export default {
  // Navigation
  'backoffice-pipeline-operations': {
    en: 'Pipeline operations',
    fr: 'Opérations pipelines',
  },
  'backoffice-pipeline-operations-description': {
    en: 'Global view of ingestion & recalculation pipelines',
    fr: "Vue globale des pipelines d'ingestion et de recalcul",
  },

  // Page
  pipeops_title: {
    en: 'Pipeline operations',
    fr: 'Opérations pipelines',
  },
  pipeops_subtitle: {
    en: 'Ingestion & recalculation pipelines across all modules and years.',
    fr: "Pipelines d'ingestion et de recalcul, tous modules et années.",
  },

  // Alert strip
  pipeops_alert_failed: {
    en: 'Failed parents',
    fr: 'Parents en échec',
  },
  pipeops_alert_errors: {
    en: 'With errors',
    fr: 'Avec erreurs',
  },
  pipeops_alert_running: {
    en: 'Running',
    fr: 'En cours',
  },
  pipeops_alert_ok: {
    en: 'Completed',
    fr: 'Terminés',
  },

  // Filters
  pipeops_filter_state: { en: 'State', fr: 'État' },
  pipeops_filter_result: { en: 'Result', fr: 'Résultat' },
  pipeops_filter_job_type: { en: 'Job type', fr: 'Type de job' },
  pipeops_filter_year: { en: 'Year', fr: 'Année' },
  pipeops_filter_has_errors: { en: 'Errors only', fr: 'Erreurs uniquement' },
  pipeops_filter_search: {
    en: 'Search status message',
    fr: 'Rechercher dans le message',
  },
  pipeops_filter_clear: { en: 'Clear filters', fr: 'Réinitialiser' },

  // Table
  pipeops_col_status: { en: 'Status', fr: 'Statut' },
  pipeops_col_pipeline: { en: 'Pipeline', fr: 'Pipeline' },
  pipeops_col_trigger: { en: 'Trigger', fr: 'Déclencheur' },
  pipeops_col_module: { en: 'Module / Year', fr: 'Module / Année' },
  pipeops_col_jobs: { en: 'Jobs', fr: 'Jobs' },
  pipeops_col_duration: { en: 'Duration', fr: 'Durée' },
  pipeops_col_when: { en: 'Started', fr: 'Démarré' },
  pipeops_col_message: { en: 'Message', fr: 'Message' },

  pipeops_status_running: { en: 'Running', fr: 'En cours' },
  pipeops_status_done: { en: 'Done', fr: 'Terminé' },
  pipeops_status_failed: { en: 'Failed', fr: 'Échec' },
  pipeops_status_partial: { en: 'Partial', fr: 'Partiel' },

  pipeops_orphan_tag: { en: '(no pipeline)', fr: '(sans pipeline)' },
  pipeops_live: { en: 'live', fr: 'live' },
  pipeops_empty: {
    en: 'No pipelines match the current filters.',
    fr: 'Aucun pipeline ne correspond aux filtres actuels.',
  },
  pipeops_loading: { en: 'Loading…', fr: 'Chargement…' },
  pipeops_refresh: { en: 'Refresh', fr: 'Actualiser' },
};
