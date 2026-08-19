---
status: draft
issue: 2050
last_updated: 2026-08-19
title: "Write-path statement budget — options A-G, 29 statements to ~7"
summary: "Spec for the interactive write path's statement-count reduction (#2050 Track I4/I5). One headcount-member POST costs 29 SQL statements after the B3 subtree fix (50 before). Twelve of them re-read three rows, because four services are each constructed with only a session and re-derive identity independently. Options A-D are pure batching (29 to 11, no UX change, no decisions needed); E folds the audit hash-chain read into an INSERT...SELECT inside the transaction; F dispatches the report and project rollups, drawing the sync/async line where work stops being proportional to the user's action; G trades the uniqueness pre-check for a unique index. Lands at ~7, the irreducible synchronous floor for 'insert an entry and return fresh module stats'. NOT YET EXECUTION-READY: per-task code and tests still to be written, see Status."
---

# Write-path statement budget: options A-G (#2050)

> **Status: SPEC, not an executable plan.** This file captures the measured
> baseline, the option set, and the design rules that constrain the work —
> everything needed so no one re-derives it. It does **not** yet carry the
> per-task TDD steps and exact code that
> [the plan format](../llm-agent-guide.md) requires for handoff to an
> implementer. See [Remaining work](#remaining-work-to-make-this-executable)
> for exactly what is missing. Do not dispatch an implementer against this
> file as it stands.

**Goal:** take one interactive `POST` of a headcount member from 29 SQL
statements to roughly 7, without giving up the caller's read-after-write
contract (their row, its emissions, their module's total).

**Spec / prior art:**
[`2050-backend-compute-performance.md`](2050-backend-compute-performance.md)
Track I4 (the measurement) and I5 (why the write stays synchronous).

**Measurement harness:**
`backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`
— counts statements through the real HTTP route on real Postgres, and
carries `STATEMENT_BUDGET` / `FACTOR_LOOKUP_BUDGET` ratchets. **Every task
below lowers a ratchet.** That is how the gain is held: the budget must
never be raised without a written reason in this file.

## Global constraints

- Ratchets only go down. A task that cannot lower `STATEMENT_BUDGET` has
  not delivered.
- Measure on **psycopg3**, never asyncpg: statement batching is
  driver-dependent, and `app/db.py` forces `postgresql+psycopg`. The harness
  already does this — do not "simplify" it back to the conftest engine.
- `distinct_factor_lookups` exists to tell "same query repeated" (a memo
  fixes it) from "a different query per leaf" (only a combined query fixes
  it). Check it before reaching for a cache. One fix in this file's history
  was already wasted by not checking it.
- The caller's read-after-write contract is **their row, its emissions,
  their module's total**. Nothing in A-G may make any of those three
  eventually-consistent.
- No new `data_entry` status field, and no "computing" state on the module.
  See [Why not dispatch the whole write](#why-not-dispatch-the-whole-write).
- Backend rules as always: `route → workflow → service → repo`, commit in
  the route, no SQL in routes, functions ≤40 lines, `col()` around column
  refs, no type suppressions, every change ships with a test.

## The measured baseline (29 statements)

Post-B3-fix. Numbering matches the harness output.

| #     | statement                                                                        | verdict                        |
| ----- | -------------------------------------------------------------------------------- | ------------------------------ |
| 1     | `SELECT carbon_reports` (report get)                                             | duplicate group                |
| 2     | `SELECT carbon_projects`                                                         | duplicate group                |
| 3     | `SELECT carbon_report_modules`                                                   | duplicate group                |
| 4     | `SELECT data_entries` — member uniqueness check                                  | business rule (G)              |
| 5     | `SELECT carbon_report_modules JOIN carbon_reports` — `fill_denormalized_scope`   | duplicate (A)                  |
| 6     | `INSERT data_entries`                                                            | **irreducible**                |
| 7     | `SELECT data_entries` — re-read of the row just inserted, for the audit snapshot | duplicate (A)                  |
| 8     | `SELECT ... JOIN carbon_projects` — `simulator_module_ids`                       | duplicate (A)                  |
| 9     | `SELECT audit_documents` — previous version, for `previous_hash`                 | fold into 10 (E)               |
| 10    | `INSERT audit_documents`                                                         | **irreducible**                |
| 11    | `SELECT audit_documents`                                                         | fold into 10 (E)               |
| 12    | `SELECT carbon_report_modules`                                                   | duplicate (A)                  |
| 13    | `SELECT carbon_reports`                                                          | duplicate (A)                  |
| 14    | `SELECT carbon_projects`                                                         | duplicate (A)                  |
| 15-17 | `SELECT factors WHERE emission_type_id IN (...)` — one per root                  | merge to 1 (C)                 |
| 18    | `SELECT data_entry_emissions` — pre-delete lookup                                | wasted on create (B)           |
| 19    | `INSERT data_entry_emissions` (batched, one statement)                           | **irreducible**                |
| 20    | `SELECT carbon_report_modules`                                                   | duplicate (A)                  |
| 21    | `SELECT ... sum(kg_co2eq), sum(additional_value)` grouped                        | **irreducible** (module stats) |
| 22    | `SELECT ... count(*)` grouped                                                    | merge with 23 (D)              |
| 23    | `SELECT ... sum(data->>'fte')` grouped                                           | merge with 22 (D)              |
| 24    | `SELECT carbon_reports`                                                          | duplicate (A)                  |
| 25    | `UPDATE carbon_report_modules` (stats)                                           | **irreducible**                |
| 26    | `SELECT carbon_report_modules`                                                   | duplicate (A)                  |
| 27    | `SELECT carbon_reports`                                                          | duplicate (A)                  |
| 28    | `SELECT carbon_reports JOIN carbon_projects`                                     | duplicate (A)                  |
| 29    | `UPDATE carbon_reports` (stats)                                                  | dispatch (F)                   |

### The dominant finding

**Twelve of 29 statements re-read three rows.**

| row                               | read at                      | times   |
| --------------------------------- | ---------------------------- | ------- |
| `carbon_reports` (one row)        | 1, 13, 24, 27, 28            | **5×**  |
| `carbon_report_modules` (one row) | 3, 12, 20, 26 (+ joins 5, 8) | **4×**  |
| `carbon_projects` (one row)       | 2, 14, 28                    | **3×**  |
| `data_entries` (just inserted)    | 7                            | re-read |

Cause: `DataEntryService`, `DataEntryEmissionService`,
`CarbonReportModuleService` and `AuditDocumentService` are each constructed
with a session only, so each re-derives identity from scratch.
`DataEntryEmissionService` even holds a `_report_by_module_id` memo — it
cannot help, because the route already resolved the same rows on a
_different instance_.

## Options A-G

| #     | change                                                                                                                       | saves   | → total |
| ----- | ---------------------------------------------------------------------------------------------------------------------------- | ------- | ------- |
| **A** | Thread the resolved `(report, project, module)` through the workflow: one join at the top, passed down instead of re-derived | **−14** | 15      |
| **B** | Skip the pre-delete `SELECT` on the create path                                                                              | −1      | 14      |
| **C** | One factor query across all roots, not one per root                                                                          | −2      | 12      |
| **D** | Merge the count and fte aggregates into one query                                                                            | −1      | 11      |
| **E** | Fold the audit hash-chain read into an `INSERT … SELECT`                                                                     | −2      | 9       |
| **F** | Dispatch the report and project rollups, coalesced by report id                                                              | −2      | 7       |
| **G** | Unique index + `ON CONFLICT` instead of the uniqueness pre-check                                                             | −1      | 6       |

A-D are mechanical and need no decision. E, F and G each carry a judgement
call, recorded below.

### E is deliberately not "move audit off the request"

The option table in the originating discussion listed E as _dispatch the
audit write_. **This spec substitutes the transactional variant, on
purpose.** Async audit means a pod death loses the audit row for an
already-committed carbon-data change, which for this project is a worse
trade than latency. The two statements audit costs beyond its `INSERT` are
the hash-chain read for `previous_hash`; computing that in SQL as part of
the insert removes the read _and_ keeps the row in the same transaction —
strictly better than dispatching. If the dispatch version is wanted
anyway, that is a decision to record here first.

### F draws the sync/async line — the rule, not the vibe

Cut where the work stops being proportional to what the user just did:

| work                          | grows with                                                                                   | verdict   |
| ----------------------------- | -------------------------------------------------------------------------------------------- | --------- |
| `INSERT data_entries`         | the one entry                                                                                | sync      |
| `INSERT data_entry_emissions` | leaves on that entry (~3-20)                                                                 | sync      |
| module stats                  | entries in _this_ module, bounded by [#2161's ceilings](2161-ceiling-scale-perf-fixtures.md) | sync      |
| report stats                  | _all modules_ in the report                                                                  | **async** |
| project stats                 | _all reports_ in the project                                                                 | **async** |

This boundary is stable as the org grows, which "what is slow today" is
not. It also needs no user-visible state: nothing the caller reads back
becomes eventually-consistent, so no `computing` badge and no new status on
`data_entry`.

**Coalescing is part of F, not a follow-up.** Ten quick edits must produce
one rollup job, not ten — otherwise F replaces 2 synchronous statements
with 10 asynchronous ones plus write contention on one `carbon_reports`
row. Check whether the runner already dedupes by scope before building it.

### Why not dispatch the whole write

Recorded so it is not re-litigated. The original proposal was to dispatch
the emission compute and all stats and show "computing" in the UI. Three
reasons it is not the plan:

1. **The cost it targeted is already gone.** 24 of the original 50
   statements were one query pattern (Strategy B3's per-leaf loop), not a
   workload. Dispatching would have moved the same 24 queries off the
   request and shown a spinner for them.
2. **A/B/C/D reach ~11 with no async at all**, so the latency argument for
   dispatching the user-visible half is spent.
3. **It re-creates Track I's failure mode with a nicer UI.** An
   `emissions: computing` state means the table, graph, module total,
   report total _and the validation gate_ must each render "not final yet"
   honestly. The validation gate is the sharp edge: a module must not be
   validatable while its stats are known-stale.

**~7 is the floor**, not a stopping point chosen for tidiness: 4
irreducible writes + one identity read + one factor query + one aggregate.
Going below it means not returning fresh module stats. True "div 10" (5
statements) is therefore out of scope by design.

## Remaining work to make this executable

Per-task TDD steps with real code are still to be written. Each needs
source read first, so that the plan states signatures rather than guessing
them:

1. **A** — read `app/workflows/carbon_report_module.py:create`,
   `resolve_report_module` in `app/api/v1/carbon_report_module.py`,
   `DataEntryService.create`, `fill_denormalized_scope`,
   `AuditDocumentService.create_version`, `simulator_module_ids`, and
   `DataEntryEmissionService._get_report_for_data_entry`. Decide the
   carrier: a small frozen dataclass passed as an argument, versus
   constructor injection on the four services. Prefer the argument — it
   does not change service lifetimes.
2. **C** — the three factor queries come from one `_fetch_factors` call per
   emission root inside `prepare_create`'s loop. Batching across roots means
   resolving all roots' subtrees before the loop, which changes
   `_fetch_factors`'s contract. Read
   `app/services/data_entry_emission_service.py` around the computation loop
   and Strategy B before writing steps.
3. **D** — read `CarbonReportModuleService.recompute_stats_many` for the
   exact shape of statements 22 and 23.
4. **E** — read `app/services/audit_service.py:create_version` for the hash
   chain, and confirm what statement 11 is.
5. **F** — read `app/tasks/` for the dispatch API
   (`fire_and_forget_or_defer_to_poller`), the aggregation handler, and
   whether job scopes already dedupe.
6. **G** — needs an Alembic migration for the unique index (via
   `make db-revision`, then prune false-positive `drop_index` calls) and a
   decision on preserving the current `DUPLICATE_INSTITUTIONAL_ID` 422.

Verification for every task: `uv run pytest tests/unit`, then
`uv run pytest tests/integration/services/data_ingestion` (one pre-existing
failure there, `test_submodule_sort_search_matrix_pg`, fails identically on
`dev` — not caused by this work), then `make lint` and `make type-check`
from the repo root.
