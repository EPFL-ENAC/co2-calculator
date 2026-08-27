---
status: delivered
issue: 1523
last_updated: 2026-07-07
title: "Fix silent recalculate failures and wrong step count in the recalculate progress UI"
summary: "Surface SSE connection errors during 'Recalculate' as a visible notification, and give recalc-triggered pipelines their own single-step phase label instead of borrowing the 3-phase ingest pipeline's 'Step 1/3 - Inserting data...' text."
---

# Fix silent recalculate failures and wrong step count in the recalculate progress UI

## Problem

Two bugs reported against the BackOffice "Recalculate" action (confirm dialog in
`ModuleRecalculationDialog.vue`, triggered via `useRecalculation.ts`):

1. **Failures aren't surfaced.** `subscribeToJobUpdates`
   (`frontend/src/stores/backofficeDataManagement.ts:469-556`) exposes two distinct
   failure signals: `onFail` (job finished with `result === ERROR`, fires a
   `Notify.create({ type: 'negative', ... })` in `useRecalculation.ts:80-90` /
   `:151-161`) and `onError` (the underlying `EventSource` itself errors — dropped
   connection, backend crash mid-stream, auth expiry — `backofficeDataManagement.ts:549-552`).
   The `onError` callback passed from `useRecalculation.ts` (`:91-93`, `:162-164`) only
   resets the `recalcRunning`/`recalcTypeRunning` flag — it never calls `Notify.create`.
   When the SSE connection drops instead of the job finishing with an explicit error, the
   spinner just stops with zero feedback: a silent failure.

2. **Wrong step count during recalculate.** Pipeline phase text isn't computed from a
   count at all — it's hardcoded per `phase_label` in
   `frontend/src/i18n/backoffice_data_management.ts:624-634`:
   `data_management_pipeline_phase_data: 'Step 1/3 - Inserting data...'`, `..._emissions:
'Step 2/3 - Recalculating emissions...'`, `..._aggregation: 'Step 3/3 - Aggregating...'`.
   These three labels are shared by every pipeline `kind` via
   `PIPELINE_PHASE_LABEL_KEYS` in `UploadCard.vue:95-99` / `ModuleConfig.vue:99-101`,
   keyed only off `PipelineProgress.phase_label` (`"data" | "emissions" |
"aggregation"`), which `compute_pipeline_progress`
   (`backend/app/services/pipeline_progress.py:120-261`) derives purely from job state
   (`phase1_done` on root FINISHED, `phase2_done` on recalc children FINISHED, `phase3_done`
   on aggregation FINISHED) — it never looks at `kind`. A `Recalculate` click creates a
   pipeline whose root job **is** the `emission_recalc` / `module_emission_recalc` job
   itself (`ensure_pipeline_exists` in `data_sync.py:1610`/`:1710`, `kind` set at that
   call — see the comment in `UploadCard.vue:101-117`), not a preceding CSV/API upload.
   While that root job is still `RUNNING`, `phase=1` => `phase_label="data"` => the UI shows
   **"Step 1/3 - Inserting data..."** even though no data is being inserted and, from the
   operator's perspective (one "Recalculate" click = one atomic action, ending in a single
   `Notify.create` in `useRecalculation.ts`), this is a one-step operation.

## Design

### Fix 1 — surface `onError` (SSE connection failure) during recalculate

`useRecalculation.ts` already distinguishes `onCompleted` / `onFail` from the bare
`onError` reset callback in both `confirmModuleRecalculation` (`:49-94`) and
`triggerTypeRecalculation` (`:120-165`). Add the same `Notify.create({ type: 'negative',
message: $t('data_management_recalculation_error'), caption: $t(<connection-lost key>) })`
call already used in the `onFail` branch to the `onError` callback, reusing the existing
`data_management_recalculation_error` i18n key (add a generic caption key, e.g.
`data_management_recalculation_connection_lost`, since no `payload` is available on a raw
`EventSource` error — distinguish it from the job-level error caption for support/debugging).
This is a store-boundary problem (the `onFail`/`onError` split already routes correctly),
not a `subscribeToJobUpdates` change — no other caller of `subscribeToJobUpdates` needs
touching, this fix is local to the two recalc call sites.

### Fix 2 — recalc-kind pipelines get their own phase vocabulary, not the ingest pipeline's "/3"

`PipelineProgress` already carries `kind` (`pipeline_progress.py:78-85`, populated from
`pipeline.kind` / root `job_type`) all the way to the frontend (`PipelineJob`/
`PipelineProgress` types, `pipelineStream`, consumed in `UploadCard.vue:147-166`). Use it:

- Backend: no change to `compute_pipeline_progress`'s phase/done math (it's correct — root
  FINISHED, recalc children FINISHED, aggregation FINISHED are still the right oracle for
  a recalc pipeline, since `module_emission_recalc` still chains one aggregation per
  Design comment at `emission_recalculation_tasks.py:590-598`). Only the **label
  vocabulary** is wrong for this `kind`; `phase`/`done`/`has_error` stay as-is.
- Frontend: in `UploadCard.vue` (and `ModuleConfig.vue`, which duplicates
  `PIPELINE_PHASE_LABEL_KEYS`), branch the label map on `p.kind`. For
  `kind === 'emission_recalc' || kind === 'module_emission_recalc'`, use a new 1-entry map
  that collapses `phase_label` "data"/"emissions" into a single
  `data_management_pipeline_phase_recalculating` key (new i18n string: `"Recalculating
emissions..."`, no "Step N/M" prefix — matches the issue's ask that a recalc read as
  `1/1`) and suppress the `"aggregation"` sub-label the same way (aggregation is an
  implementation detail invisible to whoever clicked "Recalculate", not a phase they
  triggered). Ingest (`csv_ingest`/`api_ingest`/`factor_ingest`/`reference_ingest`) pipelines
  keep the existing 3-key `PIPELINE_PHASE_LABEL_KEYS` map untouched.
- De-duplicate `PIPELINE_PHASE_LABEL_KEYS` (currently copy-pasted identically in both
  `UploadCard.vue:95-99` and `ModuleConfig.vue:99-101`) into one shared constant/composable
  while touching both files for the kind-aware map, so the new recalc map doesn't get a
  third copy to keep in sync.

## Steps

- [ ] `useRecalculation.ts`: add `Notify.create` (negative, reuse
      `data_management_recalculation_error`) inside the `onError` callback of
      `confirmModuleRecalculation` and `triggerTypeRecalculation`
- [ ] Add `data_management_recalculation_connection_lost` (en/fr) to
      `frontend/src/i18n/backoffice_data_management.ts`, used as the `Notify` caption for
      the `onError` path
- [ ] Extract `PIPELINE_PHASE_LABEL_KEYS` (currently duplicated in `UploadCard.vue` and
      `ModuleConfig.vue`) into one shared module
- [ ] Add a `kind`-aware variant: `emission_recalc` / `module_emission_recalc` map to a
      single `data_management_pipeline_phase_recalculating` label instead of the
      data/emissions/aggregation 3-step map
- [ ] Add `data_management_pipeline_phase_recalculating` (en/fr, e.g. "Recalculating
      emissions...") to `backoffice_data_management.ts`, no step-count prefix
- [ ] Update `pipelinePhaseLabelKey` computed in `UploadCard.vue` (and the equivalent in
      `ModuleConfig.vue`) to select the map by `props.pipelineProgress?.kind`
- [ ] Regression test: SSE `onerror` during a recalc job triggers a visible `Notify`
      (mock `EventSource`, assert `Notify.create` called with `type: 'negative'`)
- [ ] Regression test: a `PipelineProgress` with `kind: 'emission_recalc'` and
      `phase_label: 'data'` resolves to the recalculating label, not
      `data_management_pipeline_phase_data`
