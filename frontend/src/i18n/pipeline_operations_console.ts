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
  // Phase 3 read-flip (#1236): ``state`` filters pipeline-level
  // ``pipelines.status`` now (NOT_STARTED / RUNNING / SUCCESS /
  // PARTIAL / FAILED).  ``pipeops_filter_result`` is dropped along
  // with the URL param it labelled.
  pipeops_filter_state: { en: 'State', fr: 'État' },
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
  pipeops_col_actions: { en: 'Actions', fr: 'Actions' },

  // Per-row abort + processed-CSV download (#1080 sprint-9).
  pipeops_action_abort: { en: 'Abort pipeline', fr: 'Annuler le pipeline' },
  pipeops_action_download_csv: {
    en: 'Download processed CSV',
    fr: 'Télécharger le CSV traité',
  },
  pipeops_abort_title: { en: 'Abort pipeline?', fr: 'Annuler le pipeline ?' },
  pipeops_abort_body: {
    en: 'Every non-terminal job of this pipeline will be marked FINISHED + ERROR. In-flight handlers cooperatively stop on their next checkpoint.',
    fr: 'Chaque job non terminal de ce pipeline sera marqué FINISHED + ERROR. Les handlers en cours s’arrêtent coopérativement à leur prochain point de contrôle.',
  },
  pipeops_abort_cancel: { en: 'Cancel', fr: 'Annuler' },
  pipeops_abort_confirm: { en: 'Abort', fr: 'Confirmer' },
  pipeops_abort_success: { en: 'Pipeline aborted', fr: 'Pipeline annulé' },
  pipeops_abort_failed: {
    en: 'Failed to abort pipeline',
    fr: 'Échec de l’annulation du pipeline',
  },

  pipeops_status_running: { en: 'Running', fr: 'En cours' },
  pipeops_status_done: { en: 'Done', fr: 'Terminé' },
  pipeops_status_failed: { en: 'Failed', fr: 'Échec' },
  pipeops_status_partial: { en: 'Partial', fr: 'Partiel' },
  pipeops_status_warning: { en: 'Warning', fr: 'Avertissement' },

  pipeops_msg_click_hint: {
    en: 'Click to view the full message',
    fr: 'Cliquer pour voir le message complet',
  },
  pipeops_msg_title: { en: 'Message', fr: 'Message' },
  pipeops_msg_copy: { en: 'Copy', fr: 'Copier' },

  // #2D — phase checklist + status_history timeline rendering
  pipeops_history_toggle: { en: 'Show timeline', fr: 'Voir la chronologie' },
  pipeops_history_count: {
    en: '{n} entries',
    fr: '{n} entrées',
  },

  pipeops_orphan_tag: { en: '(no pipeline)', fr: '(sans pipeline)' },

  // Workers panel (#1080 sprint-9 observability).
  pipeops_workers_title: { en: 'Workers', fr: 'Workers' },
  pipeops_workers_count_suffix: { en: 'live', fr: 'actifs' },
  pipeops_workers_col_pod: { en: 'Pod', fr: 'Pod' },
  pipeops_workers_col_sha: { en: 'Commit', fr: 'Commit' },
  pipeops_workers_col_version: { en: 'Version', fr: 'Version' },
  pipeops_workers_col_heartbeat: { en: 'Last heartbeat', fr: 'Dernier heartbeat' },
  pipeops_workers_col_jobs: { en: 'Claimed jobs', fr: 'Jobs réservés' },
  pipeops_workers_ago: { en: 'ago', fr: '' },
  pipeops_workers_empty: {
    en: 'No live workers.',
    fr: 'Aucun worker actif.',
  },
  pipeops_workers_multi_sha_warning: {
    en: 'Multiple workers are running different commits — this can cause silent stalls (e.g. two pods racing the same job queue with mismatched logic). Verify intentional before debugging further.',
    fr: 'Plusieurs workers exécutent des commits différents — cela peut provoquer des blocages silencieux (par ex. deux pods en compétition sur la même file avec une logique divergente). Vérifier si c’est intentionnel avant d’investiguer.',
  },
  pipeops_live: { en: 'live', fr: 'live' },
  pipeops_empty: {
    en: 'No pipelines match the current filters.',
    fr: 'Aucun pipeline ne correspond aux filtres actuels.',
  },
  pipeops_loading: { en: 'Loading…', fr: 'Chargement…' },
  pipeops_refresh: { en: 'Refresh', fr: 'Actualiser' },

  // Inline phase hints rendered in the "Message" column while a
  // pipeline is still running (replaces the root job's misleading
  // ``status_message="Success"`` during the lag between csv_ingest
  // FINISHED and the chain completing).
  pipeops_phase_prefix: { en: 'Phase', fr: 'Phase' },
  pipeops_phase_data: { en: 'Data inserted', fr: 'Données insérées' },
  pipeops_phase_emissions: {
    en: 'Emissions recalculating',
    fr: 'Recalcul des émissions',
  },
  pipeops_phase_aggregation: {
    en: 'Aggregating',
    fr: 'Agrégation',
  },
};
