---
status: in-progress
issue: 2527
last_updated: 2026-08-30
summary: "Read-path items 4, 5, 6, 8 and 10 of #2527: collapse the per-report
  loops in the merged modules-stats trio and the workspace-home bundle into
  grouped queries, cache the year-configuration, and make the SQL-statement
  budget a per-PR CI gate so the next N+1 fails at review time."
---

# 2527 — read-path query counts (items 4, 5, 6, 8, 10)

Sibling plans on the same issue cover the `kg_co2eq` denormalization and the
slow write paths. This one covers **only** the read endpoints: items 4, 5, 6,
8 and 10.

## The measurement that drives everything

From #2529: the dev DB costs **~14 ms of network round-trip per query** (local
is ~0.1 ms). So for these endpoints

```
endpoint latency ≈ statement count × 14 ms
```

The slow read endpoints are the **chatty** ones, not the ones with slow
queries. The same code that answers in 26 ms locally takes 190 ms on dev — the
gap is round trips, not work.

Dev-DB medians at 50 users (unsaturated, so honest per-request cost):

| Endpoint | median @50 | p95 @200 |
| --- | ---: | ---: |
| `/v1/modules-stats/merged/report-stats` | 220 ms | **1.3 s** — first over the 1 s budget |
| `/v1/workspace/{unit}/{year}/home` | 190 ms | — |
| `/v1/unit/{unit}/{year}/totals` | 140 ms | — |
| `/v1/modules-stats/merged/multi-year-report-stats` | 110 ms | — |
| `GET /v1/session` | 90 ms | — |

### How the counts below were obtained

They are **read off the code**, not measured on a live DB — every statement is
cited by `file:line`. Task 6 (the statement-budget tests) is what turns them
into measured, asserted numbers; it lands **first** so every other task has a
before/after number rather than an estimate. Where a static count and the
measured latency disagree, that gap is called out — it is information, not
noise.

Statement counts include the `get_current_user` user lookup
(`app/core/security.py:183`), which every authenticated route pays.

---

## Task 6 — the statement-budget guardrail (do this first)

### What exists today

The mechanism is already in the repo and works. `count_statements` is a
`before_cursor_execute` event listener wrapped in a context manager, with a
`StatementLog` that tallies per table and prints a numbered statement list on
failure:

- `backend/tests/integration/services/data_ingestion/test_module_get_statement_budget_pg.py`
  (`count_statements` at lines 75–88, `STATEMENT_BUDGET = 12` at the bottom)
- `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

Both drive the **real HTTP route** through `httpx.ASGITransport` against a real
Postgres (psycopg3 — batching is driver-dependent), with auth bypassed via
`app.dependency_overrides`.

### The actual gap

**The premise of item 6 — "a new N+1 fails at PR time" — is false today.**

- Per-PR CI runs `make test-cov-xml` → `uv run pytest tests/unit` only
  (`backend/Makefile:112-114`, `.github/workflows/test.yml`).
- The two budget tests live under `tests/integration/`, reached only by
  `make test-cov-xml-integration` → `.github/workflows/integration-tests.yml`,
  which is a **daily cron**.

So a regression ships and is discovered up to 24 hours later, on a branch that
is already merged. Item 6 is therefore two parts, and the CI part is the one
that matters.

### Proposed change

**(a) Lift the shared harness.** `count_statements` / `StatementLog` are
copy-pasted in both existing files. A third caller earns the extraction — move
them verbatim into a shared conftest and import from all call sites. No
behaviour change, no new mechanism.

**(b) Land the read-path budget tests in `tests/integration/performance/`.**
That directory is already specified by plan
[`2161-ceiling-scale-perf-fixtures.md`](./2161-ceiling-scale-perf-fixtures.md)
(Task 2), which is `status: in-progress` with the suite still unwritten. Its
conftest reuses `postgres_container` / `pg_dsn` from
`tests/integration/services/data_ingestion/conftest.py` by cross-package import
— an established pattern in this repo (see
`test_factors_year_scope_pg.py`). Use the **function-scoped** `pg_dsn`: these
tests need a handful of rows, not the 21k-row ceiling fixture 2161's
session-scoped variant exists for.

**(c) Parametrize on fan-out, not just on a magic number.** A single budget
constant catches a regression only after someone tunes it. The assertion that
actually catches an N+1 is:

> the same endpoint issues the **same** number of statements for 1 unit and for
> 3 units.

So every merged-endpoint test seeds N units and asserts both `log.total <=
BUDGET` and `count(1 unit) == count(3 units)`. A loop-over-reports fails the
second assertion immediately and reads unambiguously in CI output.

**(d) Add the per-PR CI job.** Mirror the existing `test-backend-migrations`
job in `.github/workflows/test.yml` — it already spawns its own
`postgres:16-alpine` on a GitHub runner and runs a single scoped path:

```yaml
- name: Run statement-budget tests
  run: uv run pytest tests/integration/performance -vv
```

Same shape, one directory, no new infrastructure. The daily integration run
picks the same files up via normal discovery.

### Risk

Docker-in-CI on every PR adds ~1–2 minutes and one more thing that can flake.
The migration smoke job has been paying that cost already, so the precedent and
the flake rate are both known. If it proves noisy, the fallback is to keep the
job but mark it non-blocking for one week before turning it required.

### Acceptance gate

- `uv run pytest tests/integration/performance -vv` green locally and in CI.
- Each budget test prints its numbered statement list on failure (existing
  `StatementLog.numbered()` behaviour preserved).
- The fan-out assertion fails if the loop in
  `carbon_report_module_stats.py:255-257` is reintroduced — verify by
  temporarily reverting Task 4 and watching it go red.

**Budgets asserted (targets after tasks 4, 5, 8; see each task):**

| Endpoint | Today (inferred) | Budget after |
| --- | ---: | ---: |
| `/merged/report-stats` | `7 + 2R` | **≤ 9**, constant in R |
| `/merged/results-summary` | `3 + 4R` | **≤ 8**, constant in R |
| `/merged/multi-year-report-stats` | 4 | **≤ 4** (ratchet) |
| `/workspace/{unit}/{year}/home` | 10 | **≤ 7 cold / 6 warm** (statement 4 is the cached one) |
| `GET /v1/session` | 3 | **≤ 3 cold / 2 warm** |

---

## Task 4 — the merged modules-stats trio

`backend/app/api/v1/carbon_report_module_stats.py`

Throughout, **R = the number of reports resolved**, not the number of units
requested. `_authorize_and_resolve_reports` (lines 193–205) skips units with no
CALCULATOR report for that year, which is why 10 requested units
(`PERF_MERGED_UNITS=10`, `tests/performance/locustfile.py:121`) do not
reconcile with the 220 ms median — the load-test units resolve to roughly
R = 6–8.

### `/merged/report-stats` — today

| # | Statement | Site |
| --- | --- | --- |
| 1 | user lookup | `app/core/security.py:183` |
| 2 | `get_user_units` — units × unit_users × users join | `app/services/unit_service.py:102-129` |
| 3 | `list_by_units` | `app/repositories/carbon_report_repo.py:86-98` |
| 4 | IT module ids | `app/services/carbon_report_module_service.py:664-676` |
| 5–7 | `get_top_class_breakdown`, once per `_IT_TOP_CLASS_SPECS` entry present (k ≤ 3) | loop at `carbon_report_module_service.py:686-698` |
| 8… | **`build_validated_totals` × R = 2R statements** | loop at `carbon_report_module_stats.py:255-257` |

**Total `4 + k + 2R`, worst case `7 + 2R`.** At R = 8 that is 23 statements ≈
320 ms on dev — the shape of the 220 ms median and the 1.3 s p95 at 200 users.

The `2R` comes from `build_validated_totals` (lines 45–95) issuing **two**
statements per report: a report-type lookup (`:60-66`) and a module-stats read
(`:70-78`).

`query_policy("unit:query")` costs no round trip — it falls through to the
in-process branch at `app/core/policy.py:334-340`.

### `/merged/results-summary` — today (the worse one)

| # | Statement | Site |
| --- | --- | --- |
| 1–3 | user lookup, `get_user_units`, `list_by_units` | as above |
| 4… | per report: `report_repo.get` + previous-year `get_by_unit_and_year` + `_validated_module_totals` current + `_validated_module_totals` previous | `app/services/unit_totals_service.py:182, 188, 192, 198`, driven by the loop at `carbon_report_module_stats.py:288-291` |

**Total `3 + 4R`.** At R = 8 that is 35 statements ≈ 490 ms — **fatter per
request than report-stats**, but it is under-sampled in the ladder
(`@task(1)` at `locustfile.py:282` vs `@task(2)` at `:272`), so it hides behind
report-stats in the reports. The gate names report-stats; this endpoint must be
fixed in the same PR or it becomes the new worst.

One free deletion on the way: `get_results_summary(report.id)` re-fetches by id
(`unit_totals_service.py:182`) a report the caller already holds in `reports`
(`carbon_report_module_stats.py:288`).

### `/merged/multi-year-report-stats` — today

4 statements, already constant in R: user lookup, `get_user_units`,
`list_validated_buckets_by_year` (`carbon_report_repo.py:125-136`), and
`sum_stat_buckets_by_year` (`:100-123`). **This one is already fixed** — it was
grouped in a previous pass. See Task 10 for why it still measures 110 ms.

### Proposed change

The stats are already materialized JSONB. Replace both per-report loops with
one grouped read.

1. Add `CarbonReportRepository.module_stats_by_report(report_ids: list[int])`
   returning `(carbon_report_id, module_type_id, status, stats,
   carbon_report_type)` — the same three columns `build_validated_totals`
   already selects, plus the report id to fold on and the project type joined
   from `CarbonProject` (which `_calculator_reports_of` already joins). One
   statement for all R reports. **Rows come back unfiltered on `status`** —
   every consumer applies its own status rule in the Python fold. Here the only
   consumer is validated-totals, so the effect is nil; Task 5 reuses the same
   shape and *depends* on the rows being unfiltered.
2. `/merged/report-stats`: replace the loop at
   `carbon_report_module_stats.py:255-257` with one call to that repo method,
   folding per report through the existing pure helper
   `compute_validated_totals` (`app/utils/report_computations.py`). → `4 + k +
   1`, **constant in R**.
3. `/merged/results-summary`: resolve the previous year's reports with a second
   `list_by_units(unit_ids, year - 1)` (one statement, not R), then one
   `module_stats_by_report` per year. → `3 + 2 + 1 = 6`, **constant in R**.
   Drop the redundant `report_repo.get`.
4. Leave the k ≤ 3 IT top-class queries alone. Each has a different
   `group_by_field` and different `emission_type_ids`
   (`carbon_report_module_service.py:42-63`); unioning them buys ≤ 28 ms and
   costs real readability. Not worth it.

**Do not flatten `build_validated_totals` itself.** It has four call sites
(`carbon_report_module_stats.py:256, 334, 346` and `workspace_home.py:153`) and
its `validated_only` branch depends on the *per-report* project type: the
merged paths are CALCULATOR-only via `_calculator_reports_of`, the
single-report callers are not, and `SIMULATOR_EXPLORE` reports deliberately
count every module (`:68`). Keep the branch; feed it batched rows.

While moving this code: `build_validated_totals` currently executes SQL from a
route module. Moving the queries into `CarbonReportRepository` is the
`route → service → repo` layering fix a reviewer will ask for anyway, and this
is the PR that touches every line of it.

### Risk

Low — no caching, no new semantics, same JSONB source, same pure helpers
(`merge_report_stats`, `compute_validated_totals`, `compute_results_summary`)
doing the arithmetic. The one behavioural trap is the fold key: a unit can own
more than one CALCULATOR project, so `(unit, year)` may yield several reports
(`carbon_report_repo.py:90-92`). Fold on `carbon_report_id`, never on
`unit_id`.

Existing coverage to keep green: `tests/integration/v1/test_merged_report_stats.py`,
`tests/unit/utils/test_compute_results_summary.py`,
`tests/unit/services/test_unit_totals_service.py`.

### Acceptance gate

- Budget test: `/merged/report-stats` ≤ 9 statements, and equal counts for 1
  unit and 3 units.
- Budget test: `/merged/results-summary` ≤ 8 statements, and equal counts for 1
  unit and 3 units.
- `make perf-load PERF_CLASSES=ExplorerReadUser PERF_USERS=200
  PERF_MERGED_UNITS=10` against the dev DB: merged report-stats **p95 < 1 s**
  (from 1.3 s). Pin `PERF_MERGED_UNITS=10` — the merged numbers are not
  comparable across a different value.
- Response payloads byte-identical to today's for a fixed fixture (assert in
  the integration test, not by eye).

---

## Task 5 — workspace home bundle

`backend/app/api/v1/workspace_home.py` — the fattest single read in the app;
every workspace page load pays it.

### Today: 10 statements

| # | Statement | Site |
| --- | --- | --- |
| 1 | user lookup | `app/core/security.py:183` |
| 2 | `db.get(Unit, unit_id)` | `workspace_home.py:138` |
| 3 | report by unit + year | `:142` → `carbon_report_repo.py:138-155` |
| 4 | year configuration | `:148` → `:100-104` |
| 5 | `build_validated_totals` report-type lookup | `carbon_report_module_stats.py:60-66` |
| 6 | `build_validated_totals` module stats | `carbon_report_module_stats.py:70-78` |
| 7 | module states | `workspace_home.py:156-163` |
| 8 | `list_plans_by_unit` | `app/services/simulator_plan_service.py:132` |
| 9 | `list_report_stats_by_project` | `:157` |
| 10 | `get_latest_calculator_year` | `:136` |

10 × 14 ms = 140 ms, plus framework overhead ≈ the measured 190 ms. Local: 26 ms.

### Proposed change — merge queries, do not gather

**The issue's `asyncio.gather` lever is not safe as written.** SQLAlchemy's
`AsyncSession` is not usable concurrently; gathering independent awaits on the
one request-scoped session raises illegal-state errors. Making it work needs a
session — and therefore a pooled connection — per concurrent read, and #2529
establishes that the **connection budget is the binding constraint**, not CPU:
`replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` must stay under the DB's
`max_connections`, reproduced as hard failures at 4 workers × 30 vs 100.
Multiplying connections per request to save round trips trades the 200-user
problem for the 600-user problem. **Rejected.** Merge queries instead — it is
strictly cheaper and needs no concurrency at all.

1. **Merge 5 into 3.** `get_by_unit_and_year` already joins `CarbonProject`
   (`carbon_report_repo.py:142-153`). Select `carbon_report_type` in that same
   statement and hand it to the validated-totals computation. **−1**
2. **Merge 6 and 7.** Both select from `carbon_report_module` with the
   identical `carbon_report_id` predicate, and `build_validated_totals` already
   selects exactly the three columns `module_states` needs
   (`module_type_id`, `status`, `stats`). One query, two consumers. **−1**

   **The merged query must be unfiltered on `status`.** `module_states` feeds
   the sidebar timeline and the validation gates, so it needs *every* module
   row including the in-progress ones; `build_validated_totals` needs only the
   validated ones when `validated_only` (`carbon_report_module_stats.py:83`).
   That filter stays in the Python fold and must **not** be pushed into the
   `WHERE` clause — doing so silently empties the sidebar for any unit with
   unvalidated modules, which is the kind of quiet wrong answer this codebase
   forbids. Assert both consumers in the same integration test on a fixture
   that has one validated and one in-progress module.
3. **Merge 9 into 8.** `list_plans_by_unit` and `list_report_stats_by_project`
   are a parent read followed by a child read keyed on the ids the first
   returned — a join, folded in Python exactly as `_totals_by_plan` already
   folds (`simulator_plan_service.py:156-162`). **−1**
4. **Serve statement 4 from the year-config cache** built in Task 8. **−1**

**10 → 7 cold, 6 with the year-config cache warm** — ≈ 85 ms on dev, no
concurrency, no extra connections.

Leave `get_latest_calculator_year` (10) alone: it is a different question
(the unit's latest calculator year, not this year's report) and merging it
would obscure both.

### Risk

Low. Steps 1–3 are pure query merges over the same rows; the plan-totals fold
already exists. Step 4 inherits Task 8's staleness risk, addressed there.

The one thing to watch: `PlanPolicy.from_unit(current_user, unit).visible(plans)`
(`workspace_home.py:170`) filters after the fetch — the join in step 3 must not
change which plans reach it.

### Acceptance gate

- Budget test: `/workspace/{unit}/{year}/home` ≤ 7 statements (≤ 6 with the
  Task 8 cache warm; assert 7 so a cold cache does not flake the gate).
- `make perf-load PERF_CLASSES=ExplorerReadUser PERF_USERS=200`: workspace-home
  median **< 120 ms** on the dev DB (from 190 ms).
- Response payload byte-identical for a fixed fixture, including plan ordering
  (newest first) and `module_states` ordering.

---

## Task 8 — `GET /v1/session` bootstrap

`backend/app/api/v1/auth.py:555-616`. Called on every tab and every refresh.

### Today: 3 statements

| # | Statement | Site |
| --- | --- | --- |
| 1 | user lookup | `auth.py:579` → `app/core/security.py:183` |
| 2 | `get_user_units` | `auth.py:592` → `unit_service.py:102-129` |
| 3 | `list_configured_years` | `auth.py:594` → `app/api/v1/year_configuration.py:503-510` |

### The issue's role-sync lever does not apply here

3 × 14 ms = 42 ms against a measured 90 ms, so half this endpoint's cost is
**not** round trips — and it is not role sync either. `GET /v1/session` is a
pure DB read by design: ADR-017 ("`/me` is a Pure DB Read; `/refresh` Triggers
Async Role Sync") settled this, and the only
`background_tasks.add_task(trigger_role_sync_for_user, ...)` in the codebase is
in **`POST`** `/v1/session` (`auth.py:666-670`). The TTL gate the issue asks
for already exists inside `RoleSyncService.sync_user_roles`
(`app/tasks/role_sync_tasks.py:50-55`, `force=False`).

So the remaining ~48 ms is real query work, and the plausible source is
`get_user_units`: `units × unit_users × users` with a `role_priority_case`
ordering and `LIMIT 100` (`unit_service.py:102-129`). **Confirm with `EXPLAIN
(ANALYZE, BUFFERS)` on dev before optimizing it** — do not guess at an index in
this plan. If it is an index gap, that is a one-line migration; if it is the
ordering, it is a different fix. Either way it is a follow-up, not this PR.

### Proposed change: cache the year configuration

Statement 3 reads reference data that changes only when backoffice edits a
year. Cache it — and the same cache serves `build_home_year_configuration`
(`workspace_home.py:148`), so one small module buys **−1 statement on the two
hottest endpoints in the app** (~28 ms of dev round trip per page load).

Mirror the existing pattern exactly, do not invent one:

- `app/core/factor_taxonomy_cache.py` already has `_TTLCache` (LRU + TTL, no
  new dependency) — reuse it for a new `app/core/year_config_cache.py` with two
  keys: `("started", provider)` for `list_configured_years` and
  `("one", year, provider)` for `build_home_year_configuration`.
- `app/core/taxonomy_cache_broadcast.py` +
  `app/api/internal.py` already do exact cross-pod invalidation, hooked to
  commit. Reuse `schedule_taxonomy_cache_invalidation`'s shape — clear locally
  and broadcast **after** commit, never before.

### Risk — invalidation is the whole risk, so it is named explicitly

**No silent fallbacks.** A cache that serves a stale year-config after
backoffice opens a year or toggles a module would hide the change behind a TTL,
which is exactly the failure mode the project forbids. The TTL is a backstop
for a pod that missed a broadcast, **not** the correctness mechanism.

There are exactly three commit sites that write `YearConfiguration`, and all
three must clear + broadcast:

| Route | Commit |
| --- | --- |
| `POST /v1/year-configuration/` (create) | `year_configuration.py:746` |
| `PATCH /v1/year-configuration/{year}` (update) | `:910` |
| `POST .../reduction-objective-file` (upload) | `:1103` |

The three are the complete set as of this plan — a fourth writer added later
without a clear is a correctness bug, so the acceptance gate below asserts the
invalidation, not just the hit.

This cache does **not** touch the edit → chart-updates path: year config is
module visibility and thresholds, not emission data. Creating or editing an
entry does not write `YearConfiguration`.

### Acceptance gate

- Budget test: `GET /v1/session` ≤ 3 statements cold, ≤ 2 warm.
- Integration test: PATCH the year config, then immediately `GET /v1/session`
  and `GET /workspace/.../home` in the same test — both must reflect the write
  with no sleep and no TTL expiry. This is the test that would catch a missing
  clear at a fourth write site.
- `make perf-load PERF_CLASSES=ExplorerReadUser PERF_USERS=200`: session median
  **< 80 ms**.
- Follow-up issue filed with the `EXPLAIN (ANALYZE, BUFFERS)` output for
  `get_user_units` on dev, whatever it shows.

---

## Task 10 — heavy read-aggregate caching

The issue groups "unit totals" and "multi-year stats". **They have opposite
diagnoses and must be split.**

### 10a — `/v1/unit/{unit_id}/{year}/totals`: do not cache it, it is broken

`backend/app/api/v1/unit_results.py:62-91` → `UnitTotalsService.get_unit_totals`
(`app/services/unit_totals_service.py:59-127`).

**6 statements**, two of which are aggregate scans over the equipment module's
data entries — `_calculate_totals_for_year` runs twice (current year at `:79`,
previous year at `:89`), each issuing `get_by_year_and_unit` plus
`DataEntryService.get_stats`. 6 × 14 ms = 84 ms plus scan time ≈ the measured
140 ms.

**It returns `total_kg_co2eq: None` on every call.**
`DataEntryService.get_stats` is called with its defaults
(`data_entry_service.py:70-83`), so `DataEntryRepository.get_stats`
(`data_entry_repo.py:1776-1831`) groups by `data_entry_type_id` and sums
`data->'fte'`, producing a dict keyed by *stringified data-entry-type ids*.
`unit_totals_service.py:43` then reads `equipment_stats.get("total_kg_co2eq",
0.0)` — a key that cannot exist in that dict. Two bare
`except Exception` handlers (`:46-48` and `:95-97`) keep it quiet.

It also only ever considered the equipment module (`:49-55` is a TODO listing
the other six), so even fixed it would be a wrong headline.

**No caller found under `frontend/src`** — the path appears only in the
generated `frontend/src/types/api/openapi.d.ts:173`. (`/v1/unit/{id}/results`
at `:156` *is* called, from `frontend/src/stores/workspace.ts:303`, and returns
the hardcoded literal at `unit_results.py:18-44`.)

**Proposal: delete the route, or reimplement it over persisted
`carbon_report.stats` like `build_validated_totals` does — maintainer's call
(see Questions).** Caching a number that is always `None` after two table scans
is not a performance fix, and a silently-swallowed exception plus a wrong
headline is precisely what "no silent fallbacks" forbids.

Either way the 140 ms baseline in #2527 and #2529 is measuring dead code and
should be annotated as such; the locust `unit_totals` task
(`tests/performance/locustfile.py:299-304`) should drop or repoint once this is
settled, otherwise the ExplorerReadUser mix keeps spending 2 of its 11 task
weights on it.

### 10b — `/merged/multi-year-report-stats`: the one real caching candidate

Already **4 statements**, constant in R (see Task 4). 4 × 14 ms = 56 ms against
a measured **110 ms** — so unlike every other endpoint in this plan, the
round-trip heuristic does **not** explain it. The missing ~50 ms is real work:
`sum_stat_buckets_by_year` expands `json_each(stats->'buckets')` and aggregates
across every year of every requested unit (`carbon_report_repo.py:100-123`).

Fewer round trips cannot help a query that is genuinely computing. The levers
are, in order of laziness:

1. **Measure first.** `EXPLAIN (ANALYZE, BUFFERS)` on dev with
   `PERF_MERGED_UNITS=10`. If the `json_each` expansion is the cost, a GIN or
   expression index will not help and the answer is 2 or 3; if it is the
   `carbon_report`/`carbon_project` scan feeding it, an index is the whole fix
   and 2–3 are unnecessary.
2. **Short-TTL cache** keyed on the sorted `unit_ids` tuple, reusing
   `_TTLCache` from Task 8.
3. **Precomputed rollup** refreshed by the existing aggregation jobs — a
   materialized `(carbon_report_id, bucket_key, scope, total_kg)` table written
   at recompute time. Bigger change; only if 1 and 2 fall short.

**Do not start at 2 or 3.** Step 1 is an afternoon and may make the rest moot.

#### Risk — staleness, answered explicitly

The repo's rule is that creating or editing an entry updates visible charts
without leaving the page. Compare Years is a pop-up on the results page, so a
user *can* edit an entry and reopen it in the same session.

Therefore, if option 2 is taken: **the cache is invalidated by the stats write,
not by the TTL.** `CarbonReport.stats` is written by the recompute pipeline, so
the clear hooks on that write and broadcasts cross-pod via the existing
`taxonomy_cache_broadcast` mechanism, exactly as in Task 8. A TTL alone is not
acceptable here — the pipeline's own latency already delays the number, and
adding a second, invisible delay on top of it is a silent fallback.

If the invalidation hook proves awkward against the pipeline's write path,
**take option 1's index and stop**. A 110 ms endpoint that is always correct
beats a 20 ms endpoint that is sometimes wrong.

Option 3 has the same invalidation requirement and inherits the pipeline's
idempotency constraints — read the 310-series and stuck-job plans (1215, 1219,
1559, 1723) before touching anything under `app/workflows/`.

### Acceptance gate

- 10a: route deleted (or its budget test asserts a correct, non-`None` total
  from persisted stats), both bare `except Exception` handlers gone, locust mix
  updated, #2527 / #2529 annotated.
- 10b: `EXPLAIN (ANALYZE, BUFFERS)` output attached to the issue before any
  cache or rollup lands.
- 10b: budget test holds at ≤ 4 statements, constant in unit count.
- 10b if cached: an integration test that recomputes a report's stats and
  immediately re-reads `/merged/multi-year-report-stats`, with no sleep,
  asserting the new value.
- `make perf-load PERF_CLASSES=ExplorerReadUser PERF_USERS=200`: multi-year
  median **< 70 ms**.

---

## Order of work

1. **Task 6** — harness + CI job + budget tests at *today's* numbers. Every
   subsequent task then shows a measured before/after instead of an estimate,
   and the ratchet stops a regression the moment it appears.
2. **Task 4** — the only endpoint currently over the 1 s budget, and
   `/merged/results-summary` in the same PR.
3. **Task 5** — steps 1–3 (query merges). Highest per-page-load payoff.
4. **Task 8** — the year-config cache, which also finishes Task 5's step 4.
5. **Task 10a** — delete or fix; small, and it removes noise from the load-test
   baseline.
6. **Task 10b** — measure, then decide.

Ship these as separate PRs. Task 6 is a pure test/CI addition; tasks 4 and 5
change response construction and want their own reverts.

## Overall acceptance gate

```bash
# Deterministic, per PR:
uv run pytest tests/integration/performance -vv

# Against the dev DB, before promoting:
make perf-load PERF_CLASSES=ExplorerReadUser PERF_USERS=200 PERF_MERGED_UNITS=10
```

Merged report-stats **p95 under 1 s** on the dev DB at 200 users, from a
measured 1.3 s. Aggregated read p95 under the 400 ms page budget at 50 users.

## Questions for the maintainer

1. **`/v1/unit/{unit_id}/{year}/totals`** returns `None` for every field, scans
   the equipment module twice to do it, and has no caller under
   `frontend/src`. Delete the route, or reimplement it over persisted
   `carbon_report.stats`? Deleting is the smaller diff and removes two bare
   `except Exception` swallows; reimplementing keeps a public API contract that
   may have an external consumer we cannot see from this repo.
2. **Is a Docker-Postgres job on every PR acceptable?** It is the only way to
   make item 6's guardrail actually gate at PR time, and the existing
   `test-backend-migrations` job already pays that cost — but it is a second
   container per PR run.
3. **`tests/integration/performance/`** is specified but unwritten by plan 2161
   (Task 2). Landing the budget tests there means partially delivering another
   plan's scaffolding. Confirm that is preferred over adding two more files to
   `tests/integration/services/data_ingestion/` next to the existing budget
   tests, which is a smaller diff but leaves read-path tests filed under
   ingestion.
