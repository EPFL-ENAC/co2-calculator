---
status: proposed
issue: 1591
last_updated: 2026-07-07
title: "Surface per-row errors from research-facilities factor recompute"
summary: "Per-row error detail is already captured server-side when recomputing common research-facilities factors; the job just never exposes it past a bare error count, so the fix is API + frontend surfacing, not new capture logic."
---

# Surface per-row errors from research-facilities factor recompute

## Problem

Recomputing factors for the shared "common research facilities" data entry
type (DET 70) reports `"Completed with 1 error(s)"` and nothing else. The
reporter cannot tell which factor failed, why, or what to fix — even though
they can see the facilities their own unit uses.

## Design

**Per-row error detail already exists server-side — this is a surfacing gap,
not a capture gap.**

`BaseFactorUpdateProvider.ingest()`
(`backend/app/services/data_ingestion/factor_update_provider.py:138-174`)
loops all factors for `(data_entry_type_id, year)` and on each
`compute_factor_values` exception does:

```python
stats["errors"] += 1
stats["error_details"].append({"factor_id": factor.id, "error": str(e)})
```

`status_message` is then hardcoded to `f"Completed with {stats['errors']}
error(s)"` (line 171) — this exact string is what the reporter saw, verbatim,
with `error_details` computed but never attached to it.

For `research_facilities_common.py`, the raised `ValueError`s are already
actionable: `"Unit not found for researchfacility_id=..."`,
`"CarbonReport not found for unit_id=..., year=..."` — i.e. a stale or
mis-mapped `researchfacility_id` in the factors CSV, or a missing
`CarbonReport` for the resolved unit/year.

**Propagation trace (detail survives, then gets dropped at the API boundary):**

- `ingest()`'s return `data` (incl. `stats.error_details`) is flattened by
  `finalize_ingest_meta()` (`backend/app/tasks/ingestion_tasks.py:205-245`)
  into the handler's returned meta dict.
- `runner.py:206-208` takes `meta = handler_task.result()` and does
  `metadata = dict(meta)` — the full stats/error_details blob is what gets
  persisted onto the `data_ingestion_jobs` row.
- But the _read_ path the frontend actually uses —
  `RecalculationStatusEntry` (`backend/app/schemas/year_configuration.py:493-494`,
  populated from `backend/app/repositories/data_ingestion.py:1631-1632`) —
  only exposes `last_recalculation_job_id` and `last_recalculation_job_result`
  (a bare `IngestionResult` enum: SUCCESS/WARNING/ERROR). No count, no detail.
- `frontend/src/stores/yearConfig.ts:63` carries a raw `status_message?:
string` that's just the backend's `"Completed with N error(s)"` string,
  rendered as-is. `ModuleRecalculationDialog.vue` (the pre-confirm popup,
  also relevant to #1523) renders none of this — it's purely a
  trigger dialog, no error state in props or template at all.

Contrast with the Pipeline Operations Console
(`frontend/src/pages/back-office/PipelineOperationsConsolePage.vue:721-722`),
which already renders `p.error_count` from job data — the machinery for
_a_ job-error view exists, just not reachable from the unit-facing recalc
flow.

**Complication — "common" facilities are shared across units.**
`ResearchFacilitiesCommonFactorUpdateProvider.compute_factor_values`
resolves `researchfacility_id` to an arbitrary `Unit` via
`UnitRepository.get_by_institutional_id` (line 73), independent of who
triggered the recompute. A user recomputing from their own unit's view can
therefore surface an error whose `unit_id`/`CarbonReport` belongs to a
_different_ unit — the error message includes those raw IDs. Showing that
verbatim to any unit user leaks cross-unit identifiers for what is,
structurally, shared reference data they don't own.

Proposed default: keep full per-row detail (factor_id + raw exception,
including unit/report IDs) reachable only through the existing backoffice
Pipeline Operations Console (filtered by `job_id`), which already has the
permission gating and rendering for it. The unit-facing recalc surface gets
an honest, non-leaking count ("3 factors could not be recomputed") plus a
link/CTA to backoffice for anyone with that permission, and a "contact
support" hint for anyone without it. Full leak-to-triggering-user is the
alternative and simpler option, but it exposes other units' CarbonReport
existence/IDs to an arbitrary unit user — not adopted here without an
explicit product call.

## Steps

- [ ] Verify `finish_job` (or wherever `runner.py`'s `metadata` dict from
      `_run_ingest`/`factor_ingest` handler actually lands) writes
      `stats.error_details` into the persisted `data_ingestion_jobs` row —
      trace one level further than this plan did, confirm the column/JSON
      path and that it isn't truncated or dropped before commit.
- [ ] Backend: add an `error_count` (or reuse `stats.errors`) to
      `RecalculationStatusEntry` (`backend/app/schemas/year_configuration.py`)
      and its repo query (`backend/app/repositories/data_ingestion.py`
      `get_recalculation_status_by_year`), so the frontend knows "N errors"
      without a second round trip.
- [ ] Backend: confirm/extend the job-detail read path used by Pipeline
      Operations Console to accept a `job_id` for factor-recompute jobs and
      return `stats.error_details` (factor_id + message) for backoffice
      permission holders.
- [ ] Frontend: extend `RecalculationStatusEntry`/`yearConfig.ts` types with
      `error_count`, stop rendering the raw backend `status_message` string
      verbatim.
- [ ] Frontend: add a proper i18n message
      (`data_management_recalculate_completed_with_errors`, `{count}`
      interpolated) with a "view details" affordance for backoffice-permitted
      users linking to Pipeline Operations Console filtered on the job, and a
      generic non-leaking fallback for everyone else.
- [ ] Backend regression test: induce a `ValueError` in
      `ResearchFacilitiesCommonFactorUpdateProvider.compute_factor_values`
      (e.g. unmapped `researchfacility_id`) and assert `stats.error_details`
      contains the `factor_id` + message, and that it survives
      `finalize_ingest_meta` -> persisted job metadata unchanged.
- [ ] Cross-check with #1523 (same `ModuleRecalculationDialog.vue`) before
      touching the dialog, to avoid conflicting edits to the same component.
