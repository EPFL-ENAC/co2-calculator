---
status: planned
issue: 310-d
last_updated: 2026-05-07
title: "310-d Frontend — Stale-Stats UX + Pipeline SSE"
summary: "Render the in-flight bulk-pipeline state on carbon-report module cards, subscribing to GET /sync/pipelines/{id}/stream until the chain finishes."
---

# 310-d Frontend — Stale-Stats UX + Pipeline SSE

## Context

Backend half shipped in PR #1052 (SSE endpoint + `current_pipeline_id`
repo helper) and PR #1053 (provider gating + `current_pipeline_id`
field on the carbon-report response).  After a bulk CSV upload or
factor sync, `carbon_reports.stats` is stale (reflects pre-chain
data) until the runner-driven `emission_recalc → aggregation` chain
finishes.  Today the UI shows the stale numbers as if they were
fresh — operators have no signal that recalculation is in flight.

This plan ships the frontend half: a "Recalculating..." badge on
each module card, a per-pipeline SSE subscription that updates in
real time, visual de-emphasis on the stale numbers, and a clear
recovery affordance for the failure case.

## Backend prerequisites (already shipped)

- `GET /v1/carbon-reports/{id}/modules` returns
  `CarbonReportModuleRead` with `current_pipeline_id: Optional[UUID]`.
  `null` when no active pipeline → no badge.
- `GET /v1/sync/pipelines/{pipeline_id}` returns the pipeline's job
  list (one-shot read).
- `GET /v1/sync/pipelines/{pipeline_id}/stream` Server-Sent Events
  stream emitting `event: pipeline-update` payloads on any job's
  `(state, status_message, result, started_at, finished_at)` tuple
  change, plus `event: ping` heartbeats every ~15s, terminal
  `stream_closed: true` flag once every job is FINISHED.
  `populate_existing=True` on the underlying repo query so the
  long-lived AsyncSession sees out-of-band runner updates.

## Spec

### 1. Module card: "Recalculating..." badge

When `current_pipeline_id != null` on a module card:

- Show a badge near the module title (e.g. Quasar `<q-badge color="warning">`)
  with copy "Recalculating..." plus a subtle spinner / pulse animation.
- The "last updated through" timestamp on the stats block reads
  the `finished_at` of the most recent FINISHED `aggregation` job
  in the pipeline (or the previous successful aggregation if none).
- Stats numbers themselves are visually de-emphasized — gray text,
  reduced opacity (e.g. `opacity: 0.6`), maybe italic.  The numbers
  are still readable; the de-emphasis just signals "not fresh".

### 2. Pipeline SSE subscription

When the module card mounts (or when `current_pipeline_id`
transitions from `null` → set):

- Open an `EventSource` against
  `/api/v1/sync/pipelines/${current_pipeline_id}/stream`.
- On each `pipeline-update` event, update the in-memory pipeline
  state (Pinia store entry keyed by `pipeline_id`).
- The store should derive `is_finished = jobs.every(j => j.state === 'FINISHED')`
  and `has_error = jobs.some(j => j.result === 'ERROR')`.
- On `stream_closed: true` payload, close the `EventSource` —
  the backend signals end-of-stream.
- On any `EventSource.onerror` (proxy timeout, network), reopen
  with simple exponential backoff capped at 30s.

### 3. Pipeline-finished transition

When the pipeline transitions to `is_finished` (last
`pipeline-update` showed all FINISHED, or the `stream_closed`
marker arrived):

- If `has_error === false`: refetch the carbon-report response so
  the new stats land and `current_pipeline_id` clears to `null`.
  Badge disappears, stats lose their de-emphasis.
- If `has_error === true`: surface a recovery affordance — see
  section 4.

### 4. Failure recovery affordance (the meta-standpoint pinpoint)

A FINISHED+ERROR aggregation (or any FINISHED+ERROR job in the
pipeline) means the chain stopped without producing fresh stats.
The operator needs:

- A **distinguishable** badge state when the most-recent pipeline
  finished with ERROR — copy "Last recalc failed" plus a different
  color (Quasar `negative` instead of `warning`).
- A **"Retry"** button that hits the existing recalc-trigger
  endpoint (`POST /v1/sync/recalculate-emissions/{module_type_id}/{data_entry_type_id}`
  per year, or whatever the documented entry point ends up being).
- The error's `status_message` from the failed job available in
  a tooltip / detail dialog so the operator can decide whether to
  retry blindly or escalate.

This is the meta-pinpoint: chain-dispatch failures already surface
through the existing job-state metric layer (`status_message` +
structured logs).  Surfacing them in the UX is the missing piece.

### 5. Multiple modules sharing one pipeline

A `factor_ingest` fans out to N `emission_recalc` children, each
of which chains to one `aggregation` (deduplicated per `(module,
year)`).  Different modules may share a `pipeline_id`.  Implication:

- Subscribe ONCE per unique `pipeline_id` (Pinia store keyed by id),
  not once per module card mount.  Multiple cards share the same
  store entry and re-render on the same SSE update.
- The badge clears on each module independently as the
  per-module aggregation tail finishes.

## DAG: who clears the badge

```
factor_ingest (parent, module=A) -- pipeline P
    │
    ├─▶ emission_recalc (det A1) ─┐
    ├─▶ emission_recalc (det A2) ─┼──▶ aggregation (module=A, year=Y)  ← clears A's badge
    └─▶ emission_recalc (det A3) ─┘     (deduped to 1)
```

`current_pipeline_id` on module A's card returns `null` once the
aggregation row for `(A, year=Y)` reaches FINISHED — that's the
backend's `get_current_pipeline_ids_for_modules` semantics
(active = NOT_STARTED/QUEUED/RUNNING; FINISHED is excluded).

## Files (proposed)

- `frontend/src/composables/usePipelineStream.ts` (new) — wraps the
  EventSource + reconnect logic, exposes a Pinia-friendly reactive
  state.
- `frontend/src/stores/pipelineStream.ts` (new) — keyed by
  `pipeline_id`, holds `{ jobs, is_finished, has_error, status_messages }`.
- `frontend/src/components/molecules/data-management/ModuleCard.vue`
  (or wherever module cards live today — `UploadCardData.vue`,
  `UploadCardFactors.vue`, `ModuleUploadsSection.vue`) — render the
  badge + de-emphasis.
- `frontend/src/components/molecules/data-management/PipelineRetryButton.vue`
  (new) — error-state retry affordance.
- `frontend/src/types/api.ts` (or wherever `CarbonReportModuleRead`
  is typed) — add `current_pipeline_id: string | null` to the type.

## Tests

- Vitest unit on `usePipelineStream` — opens EventSource with the
  right URL, parses `pipeline-update` events into store state,
  closes on `stream_closed: true`, reopens on `onerror`.
- Vitest component test on the module card — `current_pipeline_id =
  null` → no badge; `=  uuid` → "Recalculating..." badge; FINISHED
  pipeline with `has_error` → "Last recalc failed" badge + retry
  button.
- E2E (Playwright) — full happy-path: trigger a CSV upload, observe
  badge appear, observe SSE updates, observe badge clear and stats
  refresh.

## Out of scope

- Backend changes (everything needed already shipped in #1052/#1053).
- Path 1 (interactive UI edits) — synchronous emission writes there
  remain the deliberate UX choice; no badge needed.
- Aggregating multiple pipelines per module (the backend returns the
  most-recent active pipeline only; if a follow-up factor sync chains
  while an earlier ingest is still running, the badge tracks the
  newer pipeline only).

## Risks

- **EventSource pooling on report-load**.  A report with N modules
  sharing M unique pipelines opens M streams.  M is small in practice
  (one factor upload → one pipeline → potentially every module on
  the report); shouldn't strain the browser's per-origin connection
  limit (usually 6).  Watch for it on stress test.
- **Stale `current_pipeline_id` on initial load**.  The SSE stream
  picks up updates from the moment we subscribe; if the pipeline
  finished between the carbon-report request and our subscription,
  the badge would show forever.  Mitigation: also call the one-shot
  `GET /v1/sync/pipelines/{id}` once on subscribe and apply that
  state before the stream takes over.
- **EventSource doesn't honor cookies cross-origin in some browsers**.
  The frontend is same-origin with the backend in production, so
  not a concern; flag for review if that ever changes.

## Recovery contract pin-down

For Karpathy guideline alignment: "defensive mechanisms are copium for
bad strategies".  The failure-state UX above (section 4) is NOT
defensive — it's a real product requirement.  The chain CAN fail
(DB hiccup, exception in workflow, etc.) and the user needs visible
recovery.  Backend already pinpoints failures via
`update_ingestion_job(state=FINISHED, result=ERROR, status_message=str(exc))`;
the frontend just renders that pinpoint.  This is the right place
for the failure-state UX to live, not in defensive backend code.
