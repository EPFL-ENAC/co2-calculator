---
status: review
issue: 310
title: "Plan 310 (A/B/C/D) — End-to-End Code Review of Merged Work"
last_updated: 2026-05-07
summary: "Post-merge thorough review across task system, factor pipeline, bulk-path async, API surface, frontend, migrations. Six parallel surface reviewers + spot-verification of the highest-leverage findings."
---

# Plan 310 — Post-Merge Code Review

Six parallel surface reviewers covered ~7,300 lines across 107 files merged on `dev`
between commit `dd1e870e` (Plan A) and `b801ac56` (Plan D bot-review polish).
Findings below are deduped, severity-aligned across surfaces, and the
top-tier items are individually verified against the code.

> **Headline correction.** PR #1059 shipped `tabindex="0"` + `aria-label` on the
> pipeline badges with the stated goal of opening the diagnostic tooltip on
> keyboard focus. **That deliverable does not work.** Quasar's `<q-tooltip>` only
> registers `mouseenter`/`mouseleave` (verified at
> `frontend/node_modules/quasar/src/components/tooltip/QTooltip.js:247-266`),
> so badges are now focusable but the tooltip remains hidden to keyboard-only
> users. The plan-doc claim is contradicted by the implementation. See **F-C1**
> below for the fix path.

---

## Critical (must fix before further bulk-path traffic)

### B-C1 — `update_ingestion_job` is not a CAS; the runner's pre-FINISHED preempt-check has an unguarded race window

**File**: `backend/app/repositories/data_ingestion.py:90-127`
**Verified**: yes (read the code).

The FINISHED-write path is `SELECT … WHERE id=:job_id` → mutate `state` →
`session.flush()`. There is **no** `WHERE locked_by=:pod_id AND state=RUNNING`
guard. Sequence:

1. Pod A claims job, runs handler.
2. DB hiccup → heartbeat fails (swallowed at `runner.py:231-234`).
3. Sweep on Pod B classifies row as stale, `recover_job` sets it to NOT_STARTED.
4. Pod B claims it, starts running.
5. Pod A's handler returns; runner's preempt check at `runner.py:166-187` reads
   the row and notices it's no longer locked by Pod A — **but the FINISHED
   write that follows is unconditional**. Pod A overwrites Pod B's RUNNING
   with FINISHED + Pod A's `meta`. Pod B keeps running, eventually also
   writes FINISHED, with a different `attempts` value.

Both pods complete the same work, the second pod's `meta`/`result` clobbers
the first's, and downstream chained jobs may fire twice (`chain_job` runs
inside the handler, before this race window).

**Fix**: turn the FINISHED branch in `update_ingestion_job` into an atomic
`UPDATE … WHERE id=:id AND locked_by=:pod_id AND state=RUNNING RETURNING …`.
Rowcount==0 → log+abort the runner's post-handler tail. Pair with **B-H3**
(heartbeat failure handling) to shrink the race window further.

### B-C2 — `emission_recalc` skips the aggregation chain on **any** WARNING; stats stay stale forever after a single per-entry error

**File**: `backend/app/tasks/emission_recalculation_tasks.py:110` vs `:243`
**Verified**: yes — the two handlers in the same file use inconsistent gates.

```python
# emission_recalc_handler (line 110)
if job.module_type_id is not None and result == IngestionResult.SUCCESS:
    chained_aggregation_id = await chain_job(... "aggregation" ...)

# module_emission_recalc_handler (line 243)
if final_result != IngestionResult.ERROR:
    chained_aggregation_id = await chain_job(... "aggregation" ...)
```

Single-type handler chains only on SUCCESS; module-level chains on
not-ERROR. A 10k-row factor reupload that fails on one row flips `result`
to WARNING, the aggregation chain is skipped, and `carbon_reports.stats`
stays at the pre-recalc values indefinitely — even though 9999/10000 rows
were correctly recomputed. The "Recalculating…" badge clears, the operator
sees stats unchanged, and there's no surfaced error path because
`chain_job` was never called.

**Fix**: change line 110 to `result != IngestionResult.ERROR` to match
its sibling. Add a regression test in
`tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py`
that injects a single per-entry failure and asserts the aggregation child
exists.

### F-C1 — A11y badges are focusable but the tooltip cannot open on focus

**Files**: `frontend/src/components/molecules/data-management/PipelineDiagnosticTooltip.vue:92`,
`frontend/src/components/organisms/data-management/ModuleConfig.vue:232-261`.
**Verified**: yes — `QTooltip.js:247-266` only registers `mouseenter` /
`mouseleave` (no `focus`/`blur`).

`tabindex="0"` and `aria-label` make the badge focusable and named, but
keyboard-only users cannot reach the tooltip's content (pipeline UUID,
per-job state, status messages, copy button). The PR #1059 commit message
and the 310-D plan doc claim this works; it doesn't.

**Fix path** (any of):

1. Replace `<q-tooltip>` with `<q-menu auto-close cover>` bound to
   `@focus` / `@blur` on the badge — minimal-surgery option.
2. Promote the diagnostic to a `<q-popup-proxy>` that natively supports
   focus triggers — the deferred work the plan already documents.
3. Add `aria-describedby` pointing to a hidden `<div>` containing the
   pipeline-id text so AT users get _some_ context even without the
   popup, while option 1 or 2 lands.

Whichever lands, update `310-d-frontend-stale-stats.md` to reflect the
delivered shape (the previous "Future enhancements" section honestly
flagged `<q-popup-proxy>` as future work — that prediction was correct).

---

## High

### B-H1 — Travel API `kg_co2eq` override (Tableau `OUT_CO2_CORRECTED`) is silently dropped on the async path

**File**: `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py:419-432`
**Verified**: yes — `upsert_by_data_entry` at
`backend/app/services/data_entry_emission_service.py:478-498` does **not**
accept `kg_co2eq_override`. Only `prepare_create` (line 122) does, and only
the inline branch at lines 478-503 of the provider routes through it.

Under `BULK_PATH_PURE_ASYNC=True`, the travel pipeline persists
`DataEntry` rows with `kg_co2eq` already popped from `data` (line 432),
then `EmissionRecalculationWorkflow.recalculate_for_data_entry_type`
(`workflows/emission_recalculation.py:182`) calls `upsert_by_data_entry`,
which formula-recomputes from factors. Every travel emission written via
the async path is now formula-derived, not Tableau-corrected.

This is a behaviour regression for the headline bulk-path consumer. The
provider's docstring at lines 468-473 says "the recalc workflow's
`upsert_by_data_entry` honors it via the same code path" — that comment
is empirically false.

The same risk applies to CSV-side `kg_co2eq` overrides parsed in
`base_csv_provider.py:818-829` and threaded through
`batch_kg_co2eq_overrides` — under the flag the parallel list is built
and discarded.

**Fix shape** (none cheap):

- Persist the override into `DataEntry.data` (a reserved key like
  `__kg_co2eq_override__`) and have `upsert_by_data_entry` /
  `prepare_create` look for it there.
- Or fan out a per-row override map through job `meta` into the recalc
  handler (heavier, doesn't survive recovery cleanly).

Block any further `BULK_PATH_PURE_ASYNC` rollout to travel-data tenants
until this is resolved.

### B-H2 — `LocalDataEntryCSVProvider` produces empty `data_entry_emissions` and zero `carbon_reports.stats` under the flag

**File**: `backend/app/services/data_ingestion/csv_providers/local_seed.py:446`

`_finalize_and_commit` calls `await self._recompute_module_stats()`, which
short-circuits on `BULK_PATH_PURE_ASYNC=True` (`base_csv_provider.py:1233`).
Seed scripts bypass the runner (their `_update_job` is overridden to a
no-op) so no chained `emission_recalc → aggregation` follows. Local seed
runs leave `data_entries` populated and `data_entry_emissions` empty;
every module's stats come up at zero.

This breaks dev-DB bootstrap whenever the env defaults to
`BULK_PATH_PURE_ASYNC=True`. Either the seed provider must force the
inline path explicitly, or `_recompute_module_stats` needs an
`is_seed_run` override.

### B-H3 — Heartbeat exception path is silent; a long DB outage lets the handler keep running after preemption

**File**: `backend/app/tasks/runner.py:231-234`

Heartbeat failures are swallowed with a `warning`. If the outage exceeds
`STALE_JOB_TIMEOUT_MINUTES`, a sweep on another pod recovers the row; the
current pod keeps executing the handler all the way to the FINISHED tail
(where **B-C1** then races). For a long handler this is a lot of
duplicated work — it's also the trigger for **B-C1**.

**Fix**: track consecutive heartbeat failures, abort the handler task
once they exceed `STALE_JOB_TIMEOUT_MINUTES / heartbeat_interval`.

### A-H1 — SSE handlers hold a request-scoped DB session for the full stream lifetime; pool-exhaustion risk

**File**: `backend/app/api/v1/data_sync.py:560-632` (job stream),
`:732-856` (pipeline stream)

Both endpoints take `db: AsyncSession = Depends(get_db)`. `get_db`
yields one session per request and only releases it when the dependency
exits. A pipeline stream lives until the chain finishes — easily minutes
— so each open `EventSource` pins one asyncpg pool slot. A backoffice
dashboard with N modules subscribed in parallel pins N slots.

The team's own integration test acknowledges this:
`test_sync_pipeline_stream_endpoint_pg.py:14-20` says producing a
streaming-body test "would require moving the session lifetime out of
`Depends(get_db)` for SSE endpoints — a codebase-wide refactor not in
this PR's scope." The bug is named in the test docstring.

**Fix**: have the generator open a short-lived `SessionLocal()` per poll
inside the loop and close it before `await asyncio.sleep`.

### A-H2 — SSE generators don't detect client disconnects

**File**: same as A-H1.

Neither stream takes `request: Request` nor calls
`await request.is_disconnected()`. Disconnection is only signalled when
Starlette tries to write the next event. Combined with **A-H1**, a flaky
client makes pool pressure worse.

**Fix**: take a `Request`, check `await request.is_disconnected()` at the
top of the loop. One-line change once **A-H1** has restructured the loop.

### A-H3 — Pipeline read + stream + recovery endpoints lack tenant scope

**Files**: `data_sync.py:684-690` (pipeline read), `:732-738` (stream),
`:1057-1102` (recovery), `:520-556` (cancel).

All four endpoints gate solely on global `backoffice.data_management.*`
permissions. There is no check that the pipeline's parent job is scoped
to a unit/institutional_id the caller can see. A backoffice user with
`view` permission can subscribe to or read any pipeline; a user with
`sync` permission can resurrect any tenant's stuck job.

**Conditional severity**: `project_459_backoffice_scoping` records that
sub-perimeter scoping is the _future_ of issue #459, not yet deployed.
Until that lands, this is a **latent** privilege issue. **Once #459
ships, this becomes a blocker** — every endpoint above must derive
`(module_type_id, institutional_id)` from the job and run a per-job
permission check (the `_check_module_permission_for_unit` helper at
`carbon_report_module.py:87-117` is the model). Add a per-job scoping
TODO referencing #459 in each handler now to prevent regression on the
#459 cutover.

### M-H1 — Plan B migration safety on a populated `factors` table

**File**: `backend/alembic/versions/2026_05_01_1500-b1f0a2c3d4e5_plan_310b_factor_pipeline.py`

Single transaction stacks lock-holding statements:

- L64-71 — `ALTER COLUMN ... TYPE JSONB USING classification::jsonb` (full
  rewrite under `ACCESS EXCLUSIVE`).
- L78-82 — full-table `UPDATE` retaining the lock.
- L85-96, L111-116 — `CREATE UNIQUE INDEX` / `CREATE INDEX` without
  `CONCURRENTLY` (`SHARE` lock blocking writes).
- L103-110 — `create_foreign_key` to `data_ingestion_jobs` takes
  `ACCESS EXCLUSIVE` on **both** tables — including the live job table
  the runner reads via `claim_job` — for the rest of the migration.
- L126-147 — backfill UPDATE with self-join.

The `factors` table is reference data (one row per
classification × DET × year), so the size is almost certainly
thousands, not millions — meaning this likely runs fine in the deploy
window. **The risk is not yet sized**:

- **Action**: before the next prod deploy, run `SELECT count(*) FROM
factors` against staging and a recent prod snapshot. If under ~1M
  rows, document the expected lock duration in the runbook and proceed.
  Above ~1M, split into multiple revisions: column-add (cheap), JSONB
  conversion via shadow column + dual-write + backfill, and indexes via
  `CREATE INDEX CONCURRENTLY` (requires `transaction_per_migration=False`
  - `op.execute("COMMIT")`).

The same `CONCURRENTLY`-less pattern recurs in:

- A: `e528e0d649cd_add_new_information_for_jobs.py:65-73`
  (`ix_data_ingestion_jobs_pending`)
- D: `e7f1a2b3c4d5_aggregation_dedup_index.py:71-77`
  (`uq_aggregation_active`)

Both are on `data_ingestion_jobs` — the central work-queue table — so
even short build times block every ingest/recalc HTTP endpoint and the
poller. Worth the same `CONCURRENTLY` treatment in a follow-up
maintenance migration.

### M-H2 — `is_current` partial unique index does not include `job_type`; latent silent-unclaimable risk

**Files**: `backend/app/models/data_ingestion.py:309-318`,
migration `2026_03_24_1703-253e62d79609_update_data_ingestion_index.py:39-51`

The index spans
`(module_type_id, data_entry_type_id, target_type, ingestion_method, year)
WHERE is_current=true`. Plan A/D introduced new `job_type` values
(`csv_ingest`, `factor_ingest`, `emission_recalc`, `aggregation`,
`unit_sync`). If two `job_type`s ever co-exist with overlapping
`(module, det, target_type, method, year)` and both want
`is_current=true`, the second `claim_job` trips `IntegrityError` and
silently returns `False` (`repositories/data_ingestion.py:458-459`).
The poller keeps re-selecting the row, `attempts` is not incremented,
and the job is permanently invisible.

**Action**: walk the `(target_type, ingestion_method)` cartesian against
the new `job_type` set and either add `job_type` to the partial index or
write a defended rationale that the existing keys discriminate. Pair
with **A-M1** (claim_job IntegrityError swallowing) — log at WARNING with
`job_id` so the silent-unclaimable path surfaces in production.

---

## Medium

### A-M1 — `claim_job` swallows `IntegrityError` with no log

**File**: `backend/app/repositories/data_ingestion.py:456-459`

`_ClaimUnavailable` (row was busy) and `IntegrityError` (partial unique
index race or **M-H2**) produce identical caller behavior with no log
distinguishing the two. Operations can't tell whether contention is
healthy or pathological.

**Fix**: one `logger.debug` per branch with the discriminator.

### A-M2 — `cancel_job` is read-then-write, not a CAS

**File**: `backend/app/repositories/data_ingestion.py:704-747`

Two concurrent cancellers — or cancel racing claim — both pass the
state guard then both write. Idempotent terminal transition, so
observable damage is small, but `is_current` and `meta.cancelled` get
clobbered twice.

**Fix**: atomic `UPDATE … WHERE state IN (NOT_STARTED, QUEUED, RUNNING)
RETURNING id`, mirroring `recover_job` at `:556-589`.

### B-M1 — Auto-recalc fan-out (`_chain_recalc_for_stale`) is not dedup-aware

**File**: `backend/app/tasks/ingestion_tasks.py:302-310`

Two back-to-back factor CSV reuploads for the same `(module, det, year)`
queue two `emission_recalc` children. The aggregation downstream dedups,
but the recalc itself runs twice (the expensive step). `chain_job`'s
dedup is currently hard-coded to `job_type='aggregation'`
(`_chain.py:262`); wiring `emission_recalc` dedup needs a partial
unique index on `(module_type_id, data_entry_type_id, year)` for the
active-state subset.

**Decision needed**: either intentionally allow re-runs (document) or
add the index + parameterize `chain_job`.

### B-M2 — `_chain_emission_recalc_for_data_ingest` fans out to all module dets even when CSV touched one

**File**: `backend/app/tasks/ingestion_tasks.py:323-423`

For headcount: member + student. For buildings: energy_combustion +
rooms + embodied. Each fan-out runs
`recalculate_for_data_entry_type` against its full slice. Aggregation
dedups; the expensive scans don't.

Not a correctness bug — a hot-path scan that didn't exist on the legacy
path. Worth measuring before deciding to fix.

### A-M3 — `set_started_at` is dead production code; plan-spec drift

**File**: `backend/app/repositories/data_ingestion.py:168-189`

Referenced only by tests. Production stamps `started_at` via
`func.coalesce(started_at, func.now())` baked into `claim_job` (`:445`).
Plan 310-C lists `set_started_at` as a separate runner step.

**Fix**: delete the helper and update `310-c-dag-handler-registry.md`.
The atomic-coalesce is strictly superior — no extra round trip, can't
decouple from the RUNNING transition.

### A-M4 — Sweep abandons jobs but leaves `is_current=TRUE` and `locked_by` intact

**File**: `backend/app/repositories/data_ingestion.py:530-549`
(Bucket 2 of `sweep_stuck_running_jobs`)

Abandoned rows present as `is_current=TRUE, state=FINISHED` with a
`locked_by` referencing a dead pod. Dashboards / `mark_job_as_current`
callers can't distinguish them from a healthy completion until the next
NOT_STARTED sibling demotes them.

**Fix**: mirror `cancel_job` (`:737`) — clear `is_current=False` on
abandon.

### F-M1 — `formatRelative` doesn't handle clock skew or future timestamps

**File**: `frontend/src/components/molecules/data-management/PipelineDiagnosticTooltip.vue:72-88`

Negative diffs (server clock ahead, or `started_at` in the future) fall
through every branch and produce nonsense ("-3s ago" or "0d ago"). The
`Math.round(sec/60)` boundary causes off-by-one for `sec=30..59`
(returns "1m ago", convention is "30s ago" or similar — relative-time
generally uses `Math.floor`).

**Fix**: clamp `diffMs = Math.max(0, Date.now() - then)`, return
"just now" for any non-positive delta, and switch to `Math.floor`.

### F-M2 — `showRecalcButton` predicate hides Retry on `incomplete && failed`

**File**: `frontend/src/components/organisms/data-management/ModuleConfig.vue:82-94`

If a pipeline failed AND the module became incomplete, the failure
badge shows but Retry is suppressed. Operator sees a failure with no
acknowledged path forward.

**UX call to confirm with PM**: is the intent "fix the missing upload
first, retry implicit on next factor upload"? If yes, the badge
tooltip should explicitly say so. If no, drop the
`isModuleIncomplete` short-circuit when `hasRecalcFailure` is true.

### F-M3 — Plan-doc / code drift in `usePipelineStream.ts`

**File**: `frontend/src/composables/usePipelineStream.ts`

The block at lines 38-54 (post-#f390ed4e) correctly documents that
auto-reconnect was deleted. The earlier paragraph at line 24 still says
"triggers exponential backoff reconnect capped at MAX_BACKOFF_MS." Two
paragraphs disagree on the same page.

**Fix**: 1-line edit on the next touch.

---

## Low / clean surfaces (no action)

- **Bootstrap ordering** — `app/main.py:57-67` runs `bootstrap_handlers()`
  inside `lifespan` before `yield`, before the poller starts and before
  any request lands. No "no handler registered" race.
- **N+1 fix** (commit `f68670ec`) is correctly applied at every call
  site: `CarbonReportModuleService.list_modules` and
  `_build_recalculation_status` both bulk-call
  `get_current_pipeline_ids_for_modules`.
- **i18n parity** — every new key has both en and fr; no missing
  translations.
- **Type consistency** — `current_pipeline_id` is `Optional[UUID]`
  end-to-end (backend → schema → frontend `string | null`).
- **`chain_job(dedup_active=True)` dedup** is correctly wired: NULL-scope
  guard, pre-check + `IntegrityError` fallback, partial unique index as
  ground truth.
- **JSONB key-order resilience** (the silent-duplicate-row footgun) is
  tested at runtime in `test_upsert_factors_jsonb_key_order_resilience`.
- **Permission gate on `/factors/stale`** is in place; sibling endpoints
  in the same router (`/{det}/class-subclass-map`,
  `/{det_id}/classes/{kind}/values`) pre-date 310 and are read-only
  catalog data — out of scope unless the threat model says otherwise.
- **`fire_and_forget`** holds strong refs and avoids the
  `asyncio.run`-in-sync-wrapper anti-pattern.
- **Linear alembic chain** — single head, no branching.
- **Bulk-path two-path purity** — Path 1 (`CarbonReportModuleWorkflow`)
  is correctly untouched; the gate is centralised in
  `BaseCSVProvider._process_batch`,
  `BaseCSVProvider._recompute_module_stats`, and
  `ProfessionalTravelApiProvider._load_data`.
- **`BULK_PATH_PURE_ASYNC` live-toggle**: the helper was reverted in
  `63ef8c93`; every call site now reads `get_settings()` directly. The
  docstring honestly notes a restart is required (config.py:347-356) —
  the commit message that called it "live-toggleable" is stale, but the
  code is consistent.

---

## Recommended fix order

1. **B-C1** (CAS on FINISHED write) — prevents the multi-pod corruption
   path that all other heartbeat fixes assume away.
2. **B-C2** (WARNING-skips-aggregation) — one-line fix; today every
   partial-failure recalc leaves stats stale forever.
3. **B-H1** (Travel `kg_co2eq` drop) — block bulk-path rollout to
   travel-data tenants until resolved.
4. **F-C1** (a11y tooltip) — required to redeem PR #1059's stated
   deliverable; fix on the same PR that revisits the docstring.
5. **B-H2** (seed empty stats) — silently breaks dev bootstrap; cheap
   fix.
6. **A-H1 + A-H2** (SSE session lifetime + disconnect detection) —
   refactor together; do before the dashboard is adopted broadly.
7. **A-H3** (tenant scope) — add now (TODO + per-job scope hooks),
   sharpen on #459 cutover.
8. **B-H3** (heartbeat failure handling) — paired with B-C1.
9. **M-H1** (Plan B migration on populated DB) — verify table size and
   either accept or split.
10. **M-H2** (`is_current` index + `job_type`) — confirmed cartesian or
    add the column.

Mediums batch into a single follow-up PR per surface (handlers,
repository, frontend) once the criticals/highs land.

---

## Reconciliation with already-staged follow-ups

PR #1058 (plan-only, merged) staged three architectural follow-ups as
issues #1062, #1063, #1064. Cross-checking those against the findings
above:

| Issue | Title                                                                   | Interaction with this review                                                                                                                                                                                                                                                                                                                                                 |
| ----- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #1062 | Unified frontend `pipelineStateStore`                                   | **Independent.** F-C1 (a11y) touches the same component but is orthogonal — fix F-C1 standalone, or fold into #1062 as "while you're there." #1062's own trigger ("third consumer or new field") still hasn't fired.                                                                                                                                                         |
| #1063 | Pipeline-failure observability backstop (`/v1/sync/health/stale-stats`) | **Detects, doesn't fix, B-C2 and B-H1.** `why_stale=last_aggregation_too_old` is exactly the symptom B-C2 produces; `why_stale=last_aggregation_failed` would catch B-H1's downstream drift. **Bump priority if B-C2 / B-H1 slip** — it's the insurance policy against this entire class of bug.                                                                             |
| #1064 | Generalise `chain_job(dedup_active)` to `DedupConfig`                   | **Trigger condition met.** Issue lists "progress-bar refresh" as the speculative second consumer. **B-M1 names a concrete real one**: `_chain_recalc_for_stale` (`ingestion_tasks.py:302-310`) should be dedup-aware for `emission_recalc` so back-to-back factor reuploads don't double-recalc. Promote #1064 from "wait for trigger" to "ready to schedule" — still ½-day. |

None of the eight High/Critical findings above are duplicates of the
three staged follow-ups. The architectural plan and the post-merge
review address different failure modes: the plan is forward-looking
shape work; the review is bugs in shipped code.

**Suggested issue updates**:

- Update #1064's description: trigger fired, see B-M1 of this document.
- Add a comment on #1063 cross-linking B-C2 and B-H1 as the failure
  modes it would catch passively.

## Suggested staging

Mirror the architecture-follow-ups pattern from `310-d-architecture-followups.md`:

- One **umbrella issue** "310 — post-merge review follow-ups" linking
  this document.
- **Per-finding issues** for each Critical and each High (8 total).
  Mediums folded into one or two cleanup issues per surface.
- A **draft PR** scaffolded against this document so the umbrella has a
  visible workstream.

Once the criticals are addressed, run a focused integration test pass
against `test_full_dag_pipeline_pg.py` extended to assert downstream
state (B-C2 regression test) and the multi-pod recovery race (B-C1
regression test) before declaring the 310 series fully landed.
