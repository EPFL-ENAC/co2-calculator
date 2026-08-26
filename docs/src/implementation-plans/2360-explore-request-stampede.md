---
status: delivered
issue: 2360
last_updated: 2026-08-26
title: "Explore-page request stampede: in-flight dedup + mount audit"
summary: "Dedup concurrent resolveCarbonReportId and getHeadcountMembers calls with an in-flight promise cache (11 identical report lookups and 4 identical member-roster GETs observed per explore-page load), plus a static audit of every request the simulation/explore/new mount fires and the batching opportunities it exposes."
---

## Problem

A production `TimeoutError` burst (2026-08-25, stage) traced back to the
`simulation/explore/new` page firing a request stampede on mount. A HAR
captured on stage with a **healthy backend** shows:

- **48 API calls on one page load, 35 unique endpoints, up to 34 concurrent**
  (HTTP/2).
- **11× the identical** `GET carbon-reports/simulator/explore/unit/{u}/reference-year/{y}/`
  lookup (~460 ms TTFB each — ~4.6 s of redundant backend work per load).
- **4× the identical** `GET carbon-reports/{id}/modules/headcount/members`
  (639 ms each).
- Timing split: **sum TTFB 15.1 s vs. sum blocked/queueing 0.3 s** over a
  1.6 s wall-clock window — the cost is server-side, not client queueing.

Root cause of the duplicates: `resolveCarbonReportId` in
`frontend/src/stores/modules.ts` writes its `reportIdCache` only **after** the
`await`, so every concurrent caller misses the cache and fires its own GET.
`getHeadcountMembers` in `frontend/src/api/modules.ts` had no dedup at all.

## Fix (this PR)

**In-flight promise cache** in both places — concurrent callers with the same
key share one request; the map entry is deleted in `finally`, so **rejections
are never cached** and a later call retries:

- `resolveCarbonReportId` (`frontend/src/stores/modules.ts`): a
  `Map<key, Promise<number>>` next to the existing resolved-id cache, keyed by
  the same `unit|year|project` string. The resolved-id cache behavior is
  unchanged.
- `getHeadcountMembers` (`frontend/src/api/modules.ts`): a
  `Map<carbonReportId, Promise<...>>` holding **only** the in-flight promise —
  results are deliberately not cached, so refetches after roster edits still
  hit the backend.

Regression tests (Playwright CT, `frontend/tests/unit/request-dedup.spec.ts` +
`RequestDedupHarness.vue`): 5 concurrent resolves produce exactly 1 request; a
failed lookup is retried by the next call (rejection not cached); 3 concurrent
member fetches produce 1 request while a follow-up call refetches. The CT
harness (`frontend/playwright/index.ts`) now installs Pinia and Quasar/Notify
so store-backed components mount and the ky error hooks don't crash. Both
dedup tests fail without the fix.

Effect on the HAR numbers: 11 explore lookups → **2** (the page's own
`selectSimulatorExploreCarbonReport` in the workspace store plus one shared
module-store lookup — see follow-up 1), 4 member GETs → **1**. Verified: 12 of
48 calls (~25%), ~5.9 s of stage backend time, gone.

## Audit — what one `simulation/explore/new` mount fires

Statically traced from the route (`simulation-explore`,
`meta.carbonProject: explorer`) through `workspaceGuard` →
`SimulationExplorePage` → `SubModuleSection` → `ModuleTable` / `ModuleForm` /
`HeadcountMemberSelect`, `PlannerHeadcountRows`, `PlannerResearchFacilityRows`.
The 11/4 duplicate counts predicted by this trace match the HAR exactly.

Endpoints whose stage TTFB exceeds ~320 ms (the <80 ms-local budget at
stage's ~4× factor) are marked **over budget**.

| Endpoint                                                                                                                                                                                                                                            | Fired by                                                                                                                                                                                                                         | Calls before | Calls after | Duplicates data already fetched?                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /session`                                                                                                                                                                                                                                      | auth bootstrap                                                                                                                                                                                                                   | 1            | 1           | no                                                                                                                                     |
| `GET year-configuration/`                                                                                                                                                                                                                           | `workspaceGuard` → `fetchConfiguredYears` (unconditional per guard run)                                                                                                                                                          | 1            | 1           | partly — the workspace-home aggregate also returns the selected year's config                                                          |
| `GET workspace/{unit}/{year}/home`                                                                                                                                                                                                                  | `workspaceGuard` → `fetchWorkspaceHome` (aggregate: report id, module states, year config, Calculator stats, plans)                                                                                                              | 1            | 1           | no (it exists to replace 4 calls)                                                                                                      |
| `GET carbon-reports/simulator/explore/unit/{u}/reference-year/{y}/` — **over budget (460 ms)**                                                                                                                                                      | 1× page `onMounted` via workspace store; 6× `prefetchAllModuleCounts` (one `modulePath` await per module); 2× travel `ModuleTable.onMounted`; 2× `HeadcountMemberSelect.onMounted` — the last 10 all via `resolveCarbonReportId` | **11**       | **2**       | yes — 10 of 11 were pure waste; the remaining workspace-store call and module-store call still resolve the same id twice (follow-up 1) |
| `POST` same URL (first visit only, seeds the explore report)                                                                                                                                                                                        | workspace store on 404                                                                                                                                                                                                           | 0–1          | 0–1         | no                                                                                                                                     |
| `GET carbon-reports/{id}/modules/{module}?preview_limit=0` ×6 (buildings, equipment, purchase, professional-travel, external-cloud-and-ai, process-emissions) — **purchase 871 ms, equipment 579 ms, external-cloud-and-ai 573 ms all over budget** | `prefetchSubmoduleCounts` → `prefetchAllModuleCounts`                                                                                                                                                                            | 6            | 6           | no, but 6 calls fetch one integer map each (follow-up 2)                                                                               |
| `GET modules-stats/{exploreId}/report-stats`                                                                                                                                                                                                        | page `fetchEmissionBreakdown` → `getEmissionBreakdown` (already in-flight-deduped)                                                                                                                                               | 1            | 1           | no — the guard primed the **Calculator** report's stats; the Explorer report needs its own                                             |
| `GET carbon-reports/{id}/modules/headcount/members` — **over budget (639 ms)**                                                                                                                                                                      | 2× travel `ModuleTable.onMounted` (plane, train tables) + 2× `HeadcountMemberSelect` (plane, train forms), all through the shared `getHeadcountMembers`                                                                          | **4**        | **1**       | yes — 3 of 4 were pure waste                                                                                                           |
| `GET carbon-reports/{id}/modules/headcount/planner_headcount?page=1&limit=100`                                                                                                                                                                      | `PlannerHeadcountRows.onMounted`                                                                                                                                                                                                 | 1            | 1           | no                                                                                                                                     |
| `GET factors/{70,71}/list?year={y}` ×2                                                                                                                                                                                                              | `PlannerResearchFacilityRows.onMounted` (2 groups: RF + animal facilities)                                                                                                                                                       | 2            | 2           | no                                                                                                                                     |
| `GET carbon-reports/{id}/modules/research-facilities/{sub}?page=1&limit=200` ×2                                                                                                                                                                     | `PlannerResearchFacilityRows.onMounted`                                                                                                                                                                                          | 2            | 2           | no                                                                                                                                     |
| `GET factors/{63..67}/class-subclass-map?year={y}` ×5 (purchase submodules) — **id 66 at 560 ms over budget**                                                                                                                                       | one per mounted `ModuleForm` with a class select: `useEquipmentClassOptions` fires `loadClassOptions` on setup (`watch { immediate: true }`), even inside collapsed expansion items                                              | 5            | 5           | no per id, but 5 calls to one endpoint family differing only in factor id (follow-up 3)                                                |
| `GET taxonomies/…`, remaining per-form lookups                                                                                                                                                                                                      | misc mounted forms                                                                                                                                                                                                               | ~15          | ~15         | mostly unique; static config candidates (follow-up 5)                                                                                  |

Notes:

- Submodule **tables** are collapsed by default, so `getSubmoduleData` /
  `getSubmoduleTaxonomy` do **not** fire on mount — the stampede is entirely
  prefetch + form/select setup work.
- The factors store TTL-caches per `submodule:year` but has the **same
  write-after-await gap** as `reportIdCache` had: two concurrent
  `ensureSubclassOptionMap` calls for one key both fetch. The HAR shows no
  duplicates today (one mounted form per submodule), but any second consumer
  reintroduces the stampede pattern (follow-up 4).

## Batching opportunities (deferred — new-endpoint work waits for the lead)

Per the perf budget rule: minimize XHR calls per page — extend an existing
endpoint or batch before adding a new call.

1. **Unify the two explore-report resolvers.** After this PR the page still
   resolves the explore report id twice: once through the workspace store
   (`selectSimulatorExploreCarbonReport`) and once through the module store's
   `resolveCarbonReportId`. Seeding `reportIdCache` from the workspace-store
   result (or routing the page through the module store) makes it 1. Frontend
   only, no endpoint change — natural next PR.
2. **Batch the 6 `?preview_limit=0` count calls.** Each returns one
   `data_entry_types_total_items` map. A single
   `GET carbon-reports/{id}/modules?counts=true`-style extension of an
   existing endpoint (or folding the counts into the explore-report lookup
   response) turns 6 calls (~3 s of stage TTFB, incl. the 871 ms purchase
   call) into 1.
3. **Batch the per-factor `class-subclass-map` calls.** 5 calls differ only in
   factor id; the page knows all ids at mount. A multi-id variant
   (`?factor_ids=63,64,65,66,67`) or one map keyed by factor id serves every
   form select in one round trip.
4. **In-flight dedup in the factors store** (`ensureSubclassOptionMap` /
   `ensureFactorList`): same promise-cache pattern as this PR, ~6 lines each,
   closes the latent stampede before a second consumer finds it.
5. **Ship static taxonomies/config with the bundle** where they are
   year-invariant, instead of one GET per form.
6. **Over-budget singles need backend attention regardless of batching:**
   `purchase?preview_limit=0` (871 ms), `headcount/members` (639 ms),
   `equipment` (579 ms), `external-cloud-and-ai` (573 ms),
   `class-subclass-map` id 66 (560 ms), explore lookup (460 ms) — all above
   the ~320 ms stage ceiling implied by the <80 ms-local budget.

## Testing

- `frontend/tests/unit/request-dedup.spec.ts` (Playwright CT, chromium): 3
  tests pass with the fix; the two dedup tests fail without it (5 and 4
  requests observed instead of 1).
- Root `make type-check` (ruff/ty + vue-tsc) and frontend `make lint`
  (eslint + stylelint + prettier) pass.
