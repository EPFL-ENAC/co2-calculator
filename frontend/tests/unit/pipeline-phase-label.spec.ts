/**
 * Regression test for ``resolvePipelinePhaseLabelKey`` — the pure
 * helper that picks which i18n key describes a pipeline's current
 * phase (Issue #1523).
 *
 * Before this fix, a "Recalculate" click's pipeline (root job IS the
 * ``emission_recalc`` / ``module_emission_recalc`` job itself) borrowed
 * the 3-step ingest vocabulary keyed only off ``phase_label``, so while
 * that root job was RUNNING the UI showed "Step 1/3 · Inserting data…"
 * even though nothing was being inserted. This asserts the ``kind``
 * branch takes priority and collapses to a single label, while ingest
 * ``kind``s (or no ``kind`` at all) keep the existing 3-step map.
 *
 * Pure ``(phaseLabel, kind) => key | null`` function — a pure-function
 * test is the cheapest regression guard the existing test infra
 * (Playwright, no Vitest) supports. See ``merge-live-pipeline-job.spec.ts``
 * for the identical rationale.
 */

import { test, expect } from '@playwright/test';
import { resolvePipelinePhaseLabelKey } from '../../src/composables/pipelinePhaseLabel';

test('emission_recalc kind collapses to the single recalculating label, ignoring phase_label', () => {
  expect(resolvePipelinePhaseLabelKey('data', 'emission_recalc')).toBe(
    'data_management_pipeline_phase_recalculating',
  );
  expect(resolvePipelinePhaseLabelKey('emissions', 'emission_recalc')).toBe(
    'data_management_pipeline_phase_recalculating',
  );
  expect(resolvePipelinePhaseLabelKey('aggregation', 'emission_recalc')).toBe(
    'data_management_pipeline_phase_recalculating',
  );
});

test('module_emission_recalc kind also collapses to the single recalculating label', () => {
  expect(resolvePipelinePhaseLabelKey('data', 'module_emission_recalc')).toBe(
    'data_management_pipeline_phase_recalculating',
  );
});

test('ingest kinds keep the existing 3-step phase_label map', () => {
  expect(resolvePipelinePhaseLabelKey('data', 'csv_ingest')).toBe(
    'data_management_pipeline_phase_data',
  );
  expect(resolvePipelinePhaseLabelKey('emissions', 'api_ingest')).toBe(
    'data_management_pipeline_phase_emissions',
  );
  expect(resolvePipelinePhaseLabelKey('aggregation', 'factor_ingest')).toBe(
    'data_management_pipeline_phase_aggregation',
  );
});

test('missing kind (orphan pipeline) falls back to the phase_label map', () => {
  expect(resolvePipelinePhaseLabelKey('data', null)).toBe(
    'data_management_pipeline_phase_data',
  );
  expect(resolvePipelinePhaseLabelKey('data', undefined)).toBe(
    'data_management_pipeline_phase_data',
  );
});

test('unknown phase_label with no kind resolves to null', () => {
  expect(
    resolvePipelinePhaseLabelKey('unknown' as unknown as 'data', undefined),
  ).toBeNull();
});

test('missing phase_label with no kind resolves to null', () => {
  expect(resolvePipelinePhaseLabelKey(null, undefined)).toBeNull();
  expect(resolvePipelinePhaseLabelKey(undefined, undefined)).toBeNull();
});
