---
status: in-progress
issue: 1661
last_updated: 2026-07-06
title: "Remove primary_factor_id from DataEntry.data"
summary: "Stop persisting the resolved factor id in the entry JSON; resolve factors on demand through a per-request/per-slice FactorResolver, then flip factor CSV reupload to replace-semantics so stale factor rows are deleted instead of flagged."
---

## Problem

`DataEntry.data["primary_factor_id"]` is a persisted denormalization of "which
factor matches this entry's classification". Persisting it forces an entire
invalidation apparatus, and that apparatus still leaks:

- **Stale factors cannot be deleted.** Rows missing from the latest CSV upload
  are only flagged (`GET /v1/factors/stale`, `factors.py:29`) because entry
  payloads may still hold their ids (`factor_repo.py:151`).
- **Reuploads must preserve factor ids.** `upsert_factors` keys identity on
  `(data_entry_type_id, year, emission_type_id, classification::text)` exactly
  so existing ids survive (`factor_repo.py:138`).
- **Recalc must rematch.** Plan 310B Part 6 + 310D built a bulk rematch layer
  in `emission_recalculation.py:93-262` whose only job is refreshing the
  stored id against current factors.
- **It still breaks.** When a factor's classification *shape* changes (e.g.
  building_rooms gained `energy_type` as a third classification key), the
  upsert cannot match old rows, both generations survive, and
  `get_by_classification` 500s with `MultipleResultsFound` on the first
  lookup that spans them.
- The field is internal noise: the frontend never reads it, and report
  exports explicitly scrub it (`carbon_report_module_repo.py:1238`).

## Decision

The entry's classification fields (`kind_field`, `subkind_field`,
`kind_field_override` code) are the sole source of truth. The matching factor
is **derived state**: resolved when needed, cached per request/slice, never
persisted on the entry.

`DataEntryEmission.primary_factor_id` (real FK column,
`data_entry_emission.py:1082`) is unchanged: it records the factor actually
used at computation time, is rewritten on every recalc, and backs the
results/rollup joins (`data_entry_repo.py:539,591`). Deliberately accepted
trade-off: dynamic resolution costs one bulk factor SELECT per
`(data_entry_type, year)` per request — robustness over peak performance.

## Design — Phase 1: dynamic resolution

### FactorResolver (new service)

Promote the Plan-310D lookup code out of `emission_recalculation.py:105-165`
into `app/services/factor_resolver.py`:

- One bulk SELECT per `(data_entry_type, year)`, memoized on the instance.
- In-memory resolution mirroring today's semantics exactly:
  `(kind, subkind)` match → kind-only fallback, and the override-key-first
  rule for handlers with `kind_field_override`
  (`_lookup_factor_id` / `_lookup_factor_id_with_override`).
- Instance lifetime: one API request or one recalc slice. No cross-request
  cache, no invalidation problem.

### Consumers switch to the resolver

- **Emission compute** — `prepare_create` resolves the factor and injects it
  into `ctx`; Strategy A `resolve_computations`
  (`schemas/data_entry.py:356`) keeps reading `ctx` unchanged.
  `_get_building_energy_type` receives the resolved `Factor` instead of
  dereferencing an id (`data_entry_emission_service.py:229`).
- **Create/update** — (as shipped) the create path drops factor resolution
  entirely: nothing in the create flow consumed the factor, so
  `CarbonReportModuleWorkflow.create` no longer calls the handler service
  (emission compute resolves on its own). The update path keeps a renamed
  `resolve_factor_if_changed` for its side-effects (clear subkind/override
  on kind change, repopulate defaults) with `resolve_factor` returning
  `Optional[Factor]` and never stamping. The old override-path guard that
  raised on a falsy kind moved to the validation layer:
  `PurchaseHandlerUpdate` rejects a provided-but-blank/null
  `purchase_institutional_code` (key-absent still means "not updating").
- **Recalc** — delete the rematch block (`emission_recalculation.py:192-262`);
  resolution at compute time *is* the rematch. The prefetched dicts move into
  the resolver; the strict-drop contract is preserved (no factor match →
  emission recomputes to none → dashboard missing-factor signal).
- **List enrichment** — primary path (join through the emission FK) is
  unchanged; the JSON fallback (`data_entry_repo.py:788`) resolves through
  the resolver instead, gated on the entry carrying a kind value, and
  tolerates ambiguous factor data per row (log + empty factor columns)
  instead of failing the whole list — display enrichment only; the
  compute/update paths keep surfacing ambiguity loudly.
- **CSV entry ingest** — stops writing `primary_factor_id` into row payloads
  (`base_csv_provider.py:1242-1280`); keeps its "every row must match a
  factor" validation against the same in-memory map.
- **Cleanup** — remove the export scrub (`carbon_report_module_repo.py:1238`)
  and every remaining read/write of `data["primary_factor_id"]`.

No migration: v0.x reseeds drop the DB; leftover keys in old dev rows are
dead weight ignored by all code paths.

## Design — Phase 2: replace-semantics factor ingest

With no entry-side id references, stale factor rows lose their reason to
exist (as shipped):

- `FactorRepository.delete_stale_for_year(year, *, det_ids,
  threshold_job_id)` deletes rows in the covered scope whose
  `last_seen_job_id` is NULL or predates the threshold. The threshold is
  passed explicitly by the ingest (its own job id) because mid-pipeline
  neither the running job (`state` not yet FINISHED) nor the superseded one
  (`is_current` already flipped) is visible to a job-state lookup.
- The factor CSV provider calls it right after a successful upsert, in the
  same transaction, before the 310C recalc fan-out dispatches; the deleted
  count lands in the job's `meta.stats.factors_deleted`.
- The emission FK is `ondelete="CASCADE"`: affected emission rows vanish and
  the chained recalc rebuilds them.
- `GET /v1/factors/stale`, `list_stale_for_year`, and
  `_latest_factor_job_per_det` are removed — stale rows can no longer
  exist, and with them went the generic sweep mode and its per-det SQL CASE
  threshold (no UI ever consumed the endpoint).
- The 2-key/3-key duplicate scenario (building_rooms `energy_type` reshape)
  is pinned impossible by a regression test that first reproduces the
  `MultipleResultsFound` 500, then shows the sweep killing it
  (`test_factor_replace_semantics_pg.py`).

Phase 2 ships as its own PR on top of Phase 1.

## Testing

- Regression test for the originating bug: upload 2-key building factors,
  reupload 3-key, assert the lookup returns only the new generation and the
  `/values` endpoint no longer 500s (Phase 2 makes this pass by deletion).
- `FactorResolver` unit tests inherit the existing rematch-lookup coverage
  (kind/subkind fallback chain, override-key-first, ambiguity errors).
- Strategy-B rematch integration tests repointed at the resolver path.
- Recalc integration: classification change on a factor reupload relinks
  entries through recompute alone (no stored-id refresh step).

## Out of scope

- `DataEntryEmission.primary_factor_id` column and its consumers.
- `get_by_classification` public signature (internals may gain the resolver).
- Any frontend change beyond regenerated `openapi.d.ts`.
