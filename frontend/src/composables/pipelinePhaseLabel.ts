/**
 * Pure helper: resolve which i18n key describes the current pipeline
 * phase for the "Recalculating…" badge / per-card phase indicator.
 *
 * Previously ``PIPELINE_PHASE_LABEL_KEYS`` (the 3-step ingest map) was
 * copy-pasted identically in ``UploadCard.vue`` and ``ModuleConfig.vue``,
 * keyed only off ``phase_label`` ("data"/"emissions"/"aggregation") with
 * no awareness of the pipeline's ``kind``. A "Recalculate" click on the
 * BackOffice data-management page creates a pipeline whose ROOT job IS
 * the ``emission_recalc`` / ``module_emission_recalc`` job itself (see
 * ``ensure_pipeline_exists`` calls in ``backend/app/api/v1/data_sync.py``
 * around the ``initiate*Recalculation`` endpoints), not a preceding
 * CSV/API upload. While that root job is RUNNING, ``phase_label`` is
 * still "data", so the 3-step map showed "Step 1/3 · Inserting data…"
 * even though nothing was being inserted — misleading for what is, from
 * the operator's perspective, a single-step action.
 *
 * Kept in its own leaf file (only type imports, no runtime store/Pinia
 * deps) so it can be unit-tested directly with Playwright without
 * booting the Vite-only i18n glob — same rationale as
 * ``mergeLivePipelineJob.ts``.
 */

import type { PipelineProgress } from 'src/stores/pipelineStream';

/** Ingest pipelines (csv/api/factor/reference) — unchanged 3-step vocabulary. */
export const PIPELINE_PHASE_LABEL_KEYS: Record<string, string> = {
  data: 'data_management_pipeline_phase_data',
  emissions: 'data_management_pipeline_phase_emissions',
  aggregation: 'data_management_pipeline_phase_aggregation',
};

/** Recalculate-triggered pipelines collapse to a single label — no "Step N/M". */
const RECALC_PHASE_LABEL_KEY = 'data_management_pipeline_phase_recalculating';
const RECALC_KINDS: ReadonlySet<string> = new Set([
  'emission_recalc',
  'module_emission_recalc',
]);

/**
 * Resolve the i18n key for a pipeline's current phase, or ``null`` when
 * there's nothing to show (unknown ``phase_label``, no progress yet).
 */
export function resolvePipelinePhaseLabelKey(
  phaseLabel: PipelineProgress['phase_label'] | null | undefined,
  kind: PipelineProgress['kind'] | undefined,
): string | null {
  if (kind && RECALC_KINDS.has(kind)) return RECALC_PHASE_LABEL_KEY;
  if (!phaseLabel) return null;
  return PIPELINE_PHASE_LABEL_KEYS[phaseLabel] ?? null;
}
