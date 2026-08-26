---
status: in-progress
issue: 2391
last_updated: 2026-08-26
title: "Unify factor/taxonomy option delivery: one per-year endpoint + ETag, purchase typeahead, strip coefficients"
summary: "Consolidates the seven mechanisms that feed form selects from the factors table onto the #2280 batch taxonomy endpoint (labels only, long-TTL cache + ETag), moves purchase to a server-side typeahead, and deletes the dead routes/constants the audit found. Delivered in slices; this doc tracks all seven decisions across sibling PRs."
---

## Problem

One table (`factors`) reaches form selects through **seven** delivery
mechanisms (full exploration 2026-08-26, follow-up 5 of #2360):

1. `GET factors/{det}/class-subclass-map?year=` — names only; factors store
   (in-flight dedup since #2383).
2. `GET factors/{det}/list?year=` — every row **with all coefficients**; one
   consumer bypasses the store entirely (`PlannerResearchFacilityRows.vue`);
   route missing from the committed `openapi.d.ts`.
3. `GET taxonomies/…` — the batch route `module/{module}/data-entries`
   (cached + `Cache-Control` since #2280) plus **3 single-shot routes with
   zero frontend callers** (`module_type/{x}`, `data_entry_type/{x}`,
   `module/{x}`); nodes still shipped coefficients, and the `translation_key`
   machinery was dead (never populated, echoed the code back).
4. Hardcoded `options:` arrays — ~4k lines under
   `frontend/src/constant/module-config/` duplicating backend enums/CSVs. The
   hand-mirrored `enumSubmodule` (`constant/modules.ts`) has already drifted:
   missing `building_embodied_energy = 32`.
5. Static i18n label tables — including **2.2 MB / 89k-line
   `i18n/purchase_factors.ts`** labeling the same UNSPSC codes path 1
   delivers. The DB's own description column
   (`purchase_institutional_description` in the CSV) is never ingested.
6. `building_rooms` side table — its options **override** path 1's Buildings
   subkind; one Buildings form mixes three mechanisms.
7. Misc singles (locations typeahead, exchange rates, headcount members).

Since #2385 the explore page defers all of this to first module expansion,
so the target metric is per-expansion latency and total payload, no longer a
mount stampede.

## Lifecycle invariant (settled 2026-08-26)

Operators prepare a year in the backoffice: upload factor CSVs, possibly
several times, **before** the year is opened to users. Once a year is
started, its factors never change. So per-`(data_entry_type, year)` data is
mutable during preparation and immutable after — which is what lets decision
2's cache TTL and ETag be aggressive.

## Decisions

1. **The batch taxonomy endpoint becomes THE lookup endpoint.**
   `GET taxonomies/module/{module}/data-entries?entries=…&year=` (#2280)
   already has the right shape, the server-side `(det, year)` cache,
   write-time invalidation in `FactorRepository`, cross-pod broadcast, and
   `Cache-Control`. Evolve it: strip coefficients, carry labels, and retire
   `class-subclass-map` + `/list` as frontend-facing routes once every
   consumer reads from it.
2. **Cache per the lifecycle invariant.** The 60 s TTL was sized as the
   cross-process staleness bound _before_ the broadcast existed; with exact
   cross-pod invalidation in place, raise the server TTL substantially and
   add an `ETag` (derived from the cache entry / last ingestion) so browsers
   revalidate cheaply. A started year is immutable — its responses can carry
   a long `max-age`.
3. **Strip coefficients from bulk payloads.** The only verified client
   consumer of coefficient values is the equipment form/table prefill
   (`active_power_w`/`standby_power_w`) via the narrow
   `GET factors/{det}/classes/{kind}/values?year=` (`api/factors.ts:48`,
   `ModuleForm.vue:713`, `ModuleTable.vue:639`) — kept as-is. All math stays
   server-side; raw emission factors stop being shipped to every
   authenticated user.
4. **Purchase moves to server-side search**: typeahead endpoint (shape of
   `locations/search`), 10–100 entries per response. Ingest
   `purchase_institutional_description` from the CSV as the label so the DB
   is authoritative; delete the 2.2 MB `i18n/purchase_factors.ts`.
5. **Delete dead code**: the 3 uncalled taxonomy routes, the
   `translation_key` machinery, the exported-but-uncalled `getModuleTaxonomy`
   (`stores/modules.ts`), and the stale `/list` gap in the openapi snapshot.
6. **Generate the hand-mirrored constants** from backend enums following the
   `emission-taxonomy.gen.ts` precedent (`make gen-emission-taxonomy`):
   `enumSubmodule`, room types, cabin classes, currencies, SIUS categories.
7. **One frontend discipline**: a single lookup store with in-flight promise
   dedup (pattern of #2378/#2383, largely in place) fed only by the batch
   endpoint; no component calls `api.get` for lookups directly
   (`PlannerResearchFacilityRows` is the remaining offender — it reads
   `use_unit` and other row metadata off `factors/{det}/list`, not the
   taxonomy tree, so decision 3's strip doesn't touch it; migrating it onto
   the batch endpoint + store is decision 7's remaining work).

## Open points for the plan

- Where `building_rooms` fits: fold into the unified endpoint's Buildings
  response, or keep as the one legitimate side table.
- ETag derivation: last-ingestion timestamp per `(det, year)` vs. content
  hash of the cached tree.
- Exact per-module migration order (equipment last — it carries the
  values-prefill edge case).

## Delivery checklist

- [x] **Decision 3** — strip coefficients from `TaxonomyNode`
      (`classification`/`values` dropped from the schema and the tree
      builder). All four frontend consumers (`ModuleForm.vue`,
      `ModuleInlineSelect.vue`, `ModuleTable.vue`, `PrintModuleTable.vue`)
      only ever read `name`/`label`/`translation_key`/`children` off a
      taxonomy node — verified with a repo-wide grep, no whitelist needed.
      `PlannerResearchFacilityRows.vue`'s `use_unit` read is off
      `factors/{det}/list`, not the taxonomy tree, so it's untouched here
      (see decision 7). Delivered by PR #2396.
- [x] **Decision 5, partial** — deleted the 3 uncalled taxonomy routes
      (`module_type/{x}`, `data_entry_type/{x}`, `module/{x}`) and the
      uncalled `getModuleTaxonomy` store action. Two items deferred:
      the `translation_key` machinery is _not_ removed — its only
      non-trivial source (`values.get("translation_key")`) is dead, so the
      field is now structurally identical to `name`, but four Vue
      components still branch on it and untangling that wants its own
      change + CT test rather than riding along here; the "stale `/list`
      gap in the openapi snapshot" item was already fixed by other work
      merged to `dev` earlier the same day (2026-08-26) — verified present
      in both the pre- and post-regen snapshot, not something this PR did.
      Delivered by PR #2396.
- [ ] **Decision 7 (remainder)** — move `PlannerResearchFacilityRows.vue` off
      its direct `factors/{det}/list` call onto the batch taxonomy endpoint /
      factors store. Tracked on `fix/2391-planner-rows-factors-store`.
- [ ] **Decision 1** — retire `class-subclass-map` and `/list` as
      frontend-facing routes once every consumer reads from the batch endpoint.
- [ ] **Decision 2** — raise the server TTL and add an `ETag` to the batch
      endpoint response.
- [ ] **Decision 4** — purchase server-side typeahead; ingest
      `purchase_institutional_description`; delete `i18n/purchase_factors.ts`.
- [ ] **Decision 6** — generate `enumSubmodule`, room types, cabin classes,
      currencies, SIUS categories from backend enums.

## References

- #2360 audit + follow-up 5, `docs/src/implementation-plans/2360-explore-request-stampede.md`
- #2280 / `docs/src/implementation-plans/2258-cache-factors-query.md` (the
  stack this builds on)
- Delivered siblings: #2383 (factors-store dedup), #2384 (resolver
  unification), #2385 (lazy expansion)
