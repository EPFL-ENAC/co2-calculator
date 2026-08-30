# Code review: PR #2544 — read-path query counts

Branch: `wip/2536-read-path-query-counts` · Head: `4f43c6670` · Base: `origin/dev`
Plan: #2536 / `docs/src/implementation-plans/2527-read-path-query-counts.md`
Reviewed at HIGH effort. Every number below was re-measured on this machine; none is
taken from the PR description.

## Verdict: SHIP WITH FIXES

The rewrites are semantically equivalent everywhere I could reach, the deletion is
clean in both directions, the OpenAPI artifacts regenerate byte-identically, and the
budgets are tight enough that reintroducing the real N+1 breaks them. Three fixes
before merge, all small: the comment the maintainer asked for is missing, a docstring
two files away asserts the opposite of the invariant the new fold rests on, and the
one rewrite with no test on its non-degenerate path.

---

## 1. Verification performed

Everything here is a command run on this branch, not a claim read off the PR.

### 1.1 The before/after table reproduces exactly

The PR's method — the new budget suite driving the real HTTP route against real
Postgres, with `backend/app` checked out at `origin/dev` for the "before" column — was
repeated verbatim (`git checkout origin/dev -- backend/app`, run, restore).

| Endpoint                                           | before (1 unit) | before (3 units) | after (1) | after (3) | budget |
| -------------------------------------------------- | --------------: | ---------------: | --------: | --------: | -----: |
| `/v1/modules-stats/merged/report-stats`            |               6 |               10 |         5 |         5 |      5 |
| `/v1/modules-stats/merged/results-summary`         |               6 |               14 |         4 |         4 |      4 |
| `/v1/modules-stats/merged/multi-year-report-stats` |               3 |                3 |         3 |         3 |      3 |
| `/v1/workspace/{unit}/{year}/home`                 |               8 |                — |         6 |         — |      6 |

Every cell matches the PR's table. Both merged endpoints are now flat in the report
count; `multi-year` was already grouped and is unchanged.

### 1.2 The budgets have zero headroom, and a real N+1 breaches them

This is the question that matters for a ratchet, so it was answered empirically rather
than by reading the constants: the branch's budget suite was run **against `origin/dev`'s
application code**, i.e. against the actual N+1 this PR removes.

**3 of the 4 tests fail.** Both halves of the guardrail fire independently:

- the ceilings, even at one unit — `6 > 5` (report-stats), `6 > 4` (results-summary),
  `8 > 6` (workspace home);
- the fan-out equality at three units — `10 != 6`, `14 != 6`.

So the pinned 5 / 4 / 3 / 6 are the exact measured counts with no slack, and the
regression they exist to catch does trip them. This is not a budget with room for an
N+1 to hide.

### 1.3 OpenAPI artifacts

- `app.openapi()` on this branch: 97 paths, no path containing `/totals`.
- Dumped it and compared structurally against the committed
  `frontend/scripts/openapi.snapshot.json`: **identical** (no path in one and not the
  other; whole-document equality holds).
- Ran `node frontend/scripts/gen-api-types.mjs` through the pinned
  `openapi-typescript@7.13.0`: `git status` stays clean, so the committed
  `frontend/src/types/api/openapi.d.ts` is exactly what the generator produces.

Both generated files are consistent with the code. The PR's correction to the brief is
right: `gen-constants-check` diffs only `emission-taxonomy.gen.ts` and
`module-lookups.gen.ts`, so nothing would have caught a stale snapshot — regenerating
anyway was the right call.

### 1.4 Lint and type-check

- `make lint` — green (ruff format + check, prettier backend/frontend/docs, eslint,
  stylelint, helm lint).
- `make type-check` — green (backend `ty`).
- `vue-tsc --noEmit -p tsconfig.typecheck.json` run explicitly — exit 0.

---

## 2. Do the rewritten queries return the same data?

Short answer: **yes**, with exactly one behaviour change, which the PR flags itself.
Below is each edge the rewrite could have moved.

### 2.1 Verified equivalent

**Zero-total modules — the two folds keep two different rules, correctly.**
This is the subtle part and it is right. `fold_validated_totals` keeps
`if total:` (a validated module with a 0.0 total is dropped), matching the old
`build_validated_totals` byte for byte. `_fold_results_summary` deliberately does
_not_, because plan 2096 pins that a validated module with empty stats must still
appear as a row — its docstring names the reason. Two different rules from one query,
both preserved.

**Assignment became accumulation, and that is safe.** The old
`_validated_module_totals` did `emissions[key] = total`; the new fold does
`target[key] = target.get(key, 0.0) + total`. These differ only if one report can
carry two rows for the same `module_type_id` — `uq_carbon_report_module`
UNIQUE(`carbon_report_id`, `module_type_id`) (`app/models/carbon_report.py:214`)
forbids it. Across reports the old merged route accumulated with the same `+=`, so
that half is unchanged too.

**NULLs.** `stats` NULL → `isinstance(stats, dict)` false → skipped in
`fold_validated_totals` and treated as `{}` in `_fold_results_summary`; both match the
old code. `carbon_report_type` NULL (report with no project, via the new
`outerjoin`) → `validated_only` True, exactly what the old
`scalar_one_or_none()` returning `None` produced.

**Report type resolution.** Moved from one `scalar_one_or_none()` per report to one
column per row. Within a report every row carries the same type, so the per-report
verdict is identical; grouping by `carbon_report_id` before folding preserves it.

**Reports with no module rows.** Old: the empty loop produced the zero payload. New:
absent from `by_report`, and `build_validated_totals` explicitly falls back to
`fold_validated_totals([])`. In `/merged/report-stats` the absent key contributes
nothing to the sum, which equals the `0.0` the old loop added. Same output.

**Units with no report for the year.** Both old and new derive the report set from
`list_by_units(unit_ids, year)`, so such a unit is simply absent — it contributes
neither a current figure nor a previous-year basis. Unchanged, and the docstring on
`_authorize_and_resolve_reports` says so.

**Previous-year filter.** Old `get_by_unit_and_year` and new
`list_by_units(unit_ids, year - 1)` both route through the CALCULATOR-only
`_calculator_reports_of`, so the filters are identical. The old code used
`report.year - 1` where the new uses the endpoint's `year - 1`; these agree because
`_authorize_and_resolve_reports` filters `CarbonReport.year == year`, so
`report.year == year` always.

**Ordering.** `module_stats_by_report` adds `ORDER BY carbon_report_id,
module_type_id` where the old per-report queries had none. Strictly better: the folded
payloads are now deterministic.

**The new INNER join cannot drop rows.** `module_stats_by_report` inner-joins
`CarbonReport`, where the old query hit `carbon_report_modules` alone. An orphan module
row would vanish — but `carbon_report_id` is a non-nullable
`foreign_key="carbon_reports.id"` (`app/models/carbon_report.py:173`), so there are
none.

**`list_plans_by_unit`.** The `is_grant IS FALSE` predicate correctly moved into the
outer-join `ON` clause — in the `WHERE` it would collapse to an inner join and drop
plans with no report. `has_grant` is a correlated `EXISTS` label, not a join, so the
added join does not multiply it. Plan ordering (`id DESC`) survives because dict
first-appearance order is the row order. A plan with no non-grant report yields `[]`,
and `merge_report_stats([])["total"]` is `0.0` (verified), matching the old
`by_plan[plan_id] = []` seed.

### 2.2 The one behaviour change — and the maintainer's claim, checked

`/merged/results-summary`'s previous-year basis. Old: `scalar_one_or_none()` **raised**
`MultipleResultsFound` when a unit had more than one CALCULATOR report for `year - 1`.
New: the fold sums them.

The claim that this is unreachable was verified independently rather than accepted:

**Confirmed.** `uq_carbon_projects_unit_type_calculator` is UNIQUE on
(`unit_id`, `carbon_report_type`) `WHERE carbon_report_type = 'Calculator'`, declared in
`app/models/carbon_project.py:64-70` and created in migration
`2026_08_24_1500-ff4f9bac0339`. At most one Calculator project per unit, so the
multi-project path cannot occur in production data. Summing is also the right shape on
its merits — it matches the current-year path.

Two caveats the claim does not cover, neither of which changes the verdict:

1. **The index is Postgres-only.** It carries
   `.ddl_if(dialect="postgresql")`, and the model comment says the SQLite unit-test
   schema is intentionally unconstrained here. So the state _is_ constructible in unit
   tests — the reasoning in #2544 that "the fixture would have to violate the unique
   index to exist at all" does not hold for the test schema. The decision not to add
   the fixture still stands (it would pin behaviour for a state production forbids),
   but the stated reason is only true on Postgres.

2. **An adjacent path the index does not close.**
   `uq_carbon_reports_project_year` is UNIQUE on (`carbon_project_id`, `year`,
   **`is_grant`**), and neither `list_by_units` nor `get_by_unit_and_year` filters
   `is_grant`. One Calculator project holding both a grant and a non-grant report for
   the same year therefore yields two rows — old raised, new sums silently. Checked
   the write sites: `is_grant=True` is set in exactly one place,
   `simulator_plan_service.py:341`, on a plan project. So this is unreachable **by code
   path**, not by schema — a weaker guarantee than the multi-project case, and worth
   the one line of comment below.

---

## 3. The deletion of `/v1/unit/{unit_id}/{year}/totals`

Clean. Confirmed independently in every direction the brief asked for.

- **Backend**: no reference to `get_unit_totals`, `_calculate_totals_for_year`,
  `_validated_module_totals`, `_totals_by_plan` or `list_report_stats_by_project`
  survives anywhere under `backend/app` or `backend/tests`.
- **Frontend**: no reference under `frontend/src` outside the generated
  `openapi.d.ts`, which no longer names the route. The surviving `getModuleTotals` hits
  (`stores/modules.ts:884/950/995`, `PlannerYearSection.vue:934`, `ModulePage.vue:89`)
  all resolve to the 4-argument function defined locally at `stores/modules.ts:567` —
  a different symbol from the deleted 2-argument `api/modules.ts` export.
  `ModuleTotalsResponse` has no referrer. `buildModuleTotalsResponse` in
  `tests/integration/setup/simulator-mocks.ts` is an unrelated local helper.
- **The dead-code claim substantiated**: `DataEntryService.get_stats` defaults
  `aggregate_by="data_entry_type_id"` (`app/services/data_entry_service.py:70-76`), so
  the returned dict is keyed by stringified type ids and
  `equipment_stats.get("total_kg_co2eq", 0.0)` could never hit. The endpoint returned
  `None` for every field on every call. Deleting rather than repairing is the right
  call — even fixed it only ever summed the equipment module, so it was a wrong
  headline by construction.
- **Locust**: the task is dropped from `ExplorerReadUser`, freeing 2 of 11 task weights
  that were measuring dead code.
- Only historical plan documents still mention the route (see nit N3).

---

## 4. Statement-budget tests

**Are the pinned numbers what the code issues?** Yes — 5 / 4 / 3 / 6, measured above,
with the suite passing 4/4 on this branch. **Would a real N+1 breach them?** Yes —
demonstrated in §1.2 by running the same suite against `origin/dev`'s application code.

Structure is sound: every merged endpoint is asserted twice, once against a ceiling and
once for equality between one unit and three. The equality assertion is the one that
reads unambiguously in CI, and it is the one that catches a reintroduced loop the
moment it appears rather than after someone tunes a constant.

Two details worth naming as good:

- `count_statements` listens on `before_cursor_execute`, the only layer that sees what
  the driver actually sends — an ORM-level count would under-report, since psycopg3
  batches round trips.
- The fixture seeds one validated and one in-progress module per report, so
  `test_workspace_home_statement_budget` asserts _both_ consumers of the single read:
  the sidebar keeps the in-progress module while the headline counts only the validated
  one. A future push-down of the status filter into the `WHERE` clause goes red instead
  of silently emptying the sidebar. That is the right test for the right risk.

The conftest picking its own container name and port (55434, distinct from
`data_ingestion`'s 55432 and the alembic smoke's 55433) is correct and the reasoning is
written down. Because it builds the schema with `SQLModel.metadata.create_all` on
Postgres, the partial unique indexes from §2.2 _are_ present in the budget suite.

Gap: see F3 — the plan-list rewrite is not covered by these fixtures.

---

## 5. The CI job

Scoped as the maintainer required, and it already ran.

- **Trigger**: `.github/workflows/test.yml` declares
  `on: pull_request: branches: [main, dev, stage]`. PRs target `dev`, so the job runs on
  every PR. Confirmed on the real thing rather than inferred from the YAML:
  `gh pr checks 2544` lists **`Backend Statement Budgets (read-path query counts)` —
  SUCCESS**. So Docker-in-CI, the fixed host port 55434, and the `.env` seeding all work
  on a GitHub runner, none of which local verification could have shown.
- **Scope**: the run step is `uv run pytest tests/integration/performance -vv` — the
  four statement-budget tests and nothing else. That file contains no timing assertion,
  no locust invocation, and no ceiling fixture. Matches the decision in #2536 exactly.
- **Shape**: mirrors `test-backend-migrations` (the suite spawns its own
  `postgres:16-alpine`, no service container), and seeds `.env` with
  `cp .env.example .env` the way `gen-constants-check` does — necessary, because the
  conftest imports `app.main`, which constructs `Settings`. Verified locally: without
  the `.env` the suite cannot import.

Costs a container start plus ~4 s of tests. Cheap for a guardrail that otherwise only
fires on the daily cron, a day after the regression merged.

---

## 6. Repo invariants

| Invariant                | Verdict                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| No silent fallbacks      | Both bare `except Exception` swallows are gone with the dead route. **No `except Exception` remains in any file this PR touches.** (92 remain repo-wide — all pre-existing, none in this diff.)                                                                                                                                                                                                                                                                          |
| `col()` on SQLModel refs | Every new column reference in the diff is wrapped. The bare comparisons in `_calculator_reports_of` and `list_plans_by_unit`'s `where` are pre-existing lines, unchanged.                                                                                                                                                                                                                                                                                                |
| Functions ≤ 40 lines     | Every function this PR adds is well under. The over-length functions in the touched files (`get_workspace_home` 48, `compute_results_summary` 99, the `simulator_plan_service` block) are all pre-existing — and `get_workspace_home` gets _shorter_ here.                                                                                                                                                                                                               |
| Route → service → repo   | Improved, not fully clean. The PR removes inline `select()` from `carbon_report_module_stats.py` entirely, which is the right direction. Two route-module helpers now call a repository directly (`build_validated_totals_by_report`, and `workspace_home.py` calling `CarbonReportRepository(db).module_stats_by_report`) — no SQL in the route, but the service layer is skipped. Both replace code that built SQL in the route module, so this is a net gain; see N4. |
| Migrations               | None in this PR.                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Plan alignment           | Plan 2161 is updated to record that its Task 2 scaffolding shipped here and how the delivered fixtures differ. Good. See N3 for the one stale reference left elsewhere.                                                                                                                                                                                                                                                                                                  |

---

## Fixes required before merge

### F1 — the comment the maintainer explicitly asked for is missing

#2536's answer asked for "a one-line comment at the fold naming
`uq_carbon_projects_unit_type_calculator` as the reason a multi-project unit cannot
occur — so the next reader doesn't re-derive this, and so anyone who later relaxes that
index sees what depends on it."

`uq_carbon_projects_unit_type_calculator` appears nowhere under `backend/app/` except
its own definition in `app/models/carbon_project.py`. Neither
`UnitTotalsService.get_merged_results_summary` nor `_fold_results_summary` names it.

Add it at the fold. Worth including the §2.2 caveat in the same line: the index closes
the multi-_project_ case by schema; the grant/non-grant pair for one year is closed only
by there being a single `is_grant=True` write site, which is a code-path guarantee, not
a schema one.

### F2 — a docstring asserts the opposite of the invariant the new fold rests on

`backend/app/repositories/carbon_report_repo.py:92-93`, on `list_by_units`:

> A unit can own more than one Calculator project, so a (unit, year) pair may yield
> several reports; callers fold them.

That is false on Postgres, per the index verified in §2.2. It is pre-existing on `dev`,
but this PR makes `get_merged_results_summary` the caller that folds, so the sentence is
now load-bearing misinformation sitting two files from the code whose safety depends on
it being wrong. The PR description repeats it (behaviour-change note 3: "a unit can own
more than one CALCULATOR project").

Keying the fold on `carbon_report_id` rather than `unit_id` is still the right choice —
the `is_grant` pair in §2.2 is a real second-row source. Keep the key; correct the
stated reason, in the docstring and in the PR description.

### F3 — `list_plans_by_unit` has no test on its non-degenerate path

This is the one rewrite in the PR whose interesting behaviour nothing exercises. Its
return type changed from a 3-tuple to a 4-tuple and the per-plan stats query was folded
into the plans query, but:

- `tests/unit/services/test_simulator_plan_service.py:138`
  (`test_list_plans_scoped_to_unit`) creates plans with **no** year reports and asserts
  only their names — it runs the `report_stats == []` branch;
- the budget fixture `_seed_units` seeds **no plans at all**, so workspace home's
  statement 5 executes the new outer join against zero rows.

So the grouping (one plan, two non-grant year reports → one entry carrying two stats
dicts), the `is_grant` exclusion now living in the `ON` clause, and the `id DESC`
ordering under duplicated project rows are all untested on either side of the change.
The guardrail is explicit: every change ships with a test on the side it touches.

One unit test covers it: a plan with two year reports plus a grant report, asserting the
returned total is the sum of the two non-grant reports (grant excluded) and that plan
order is newest-first. Cheap, and it is the assertion that would catch the `ON`-clause
predicate drifting into the `WHERE`.

---

## Nits (non-blocking)

**N1.** The three single-report endpoints `/{carbon_report_id}/report-stats`,
`/validated-totals` and `/results-summary` all changed shape here (results-summary drops
from 4 statements to 3) and none is budget-pinned. They contain no loop over reports, so
there is no fan-out risk; a fourth ratchet would be cheap but is not required by the
plan.

**N2.** `list_plans_by_unit` has no `ORDER BY` on the aliased `year_report`, so the
order of a plan's `report_stats` list is not deterministic. Only `["total"]` is read, and
summing is order-independent, so this is harmless today. Noting it because
`module_stats_by_report` right next door added an `ORDER BY` for exactly this reason —
the asymmetry invites a future order-sensitive consumer.

**N3.** `docs/src/implementation-plans/977-tighten-unit-permission-gates.md` still lists
`get_unit_totals` as a gated endpoint in three places. It is a historical record of what
shipped then, so leaving it is defensible; a one-line "removed in #2544" would keep the
delivered-plan set honest.

**N4.** `backend/app/api/v1/workspace_home.py:100` still builds a raw
`select(YearConfiguration)` in the route module. Pre-existing, and this PR moves that
file toward compliance rather than away — flagged only so the "no SQL in routes"
invariant is not recorded as clean when it is not.

**N5.** `get_workspace_home` remains 48 lines, over the ≤40 cap. Pre-existing; the PR
shortens it. Not introduced here.

---

## On what was deliberately left out

Both exclusions are correctly argued and should stay out.

- **Task 8 (year-config cache)** — workspace home reaches its target without it, and a
  cache serving a stale year config behind a TTL is precisely the silent fallback this
  codebase forbids. Its invalidation surface (three `YearConfiguration` write sites plus
  cross-pod broadcast) is not "straightforward".
- **Task 10b (multi-year caching)** — the endpoint is already 3 statements and constant
  in the report count, so the remaining latency is query work that fewer round trips
  cannot fix. Its own acceptance gate requires `EXPLAIN (ANALYZE, BUFFERS)` first.
  Measure before caching is the right order.

The rejection of the plan's `asyncio.gather` lever is also right and worth keeping
written down: `AsyncSession` is not concurrency-safe, and gathering costs a pooled
connection per read when #2529 established the pool as the binding constraint.
