---
status: delivered
issue: 1491
last_updated: 2026-07-10
title: "Factor Upsert Strategy — Re-scoped: keep the upsert, harden it, ship viewer + bulk delete"
summary: "The duplicate-factor bug that motivated #1491 is structurally fixed by the 310B upsert + stale sweep, and plan 1661 removed the original reason id-stability was load-bearing. Decided scope (maintainer, 2026-07-10): keep the upsert and make it stronger — null-identity guard, semantics write-up, backoffice factor viewer, bulk delete endpoints."
---

# Factor Upsert Strategy — Re-scoped Plan (supersedes the 2026-07-07 draft)

## Why this rewrite

Maintainer prompt: "we deleted the primary_factor_id and we don't do upsert anymore.
Review if it's even necessary still to do so."

**Maintainer decisions (2026-07-10), binding for this plan:** the recollection
referred to plan 1661's removal of the persisted-FK rematch (confirmed); the
upsert stays and gets hardened; the issue stays open re-scoped to asks 2–4
below (no close/re-file); related issues #828 and #421 have been closed as
resolved by 1661 + the current upsert.

Verified against `dev` tip (2026-07-10, includes the stat-bucket refactor `42186e8c`):

- **`primary_factor_id` — deleted from `DataEntry.data` only.** Plan 1661
  (commit `5293bbd5`, data migration
  `backend/alembic/versions/2026_07_06_1124-954eac6c95da_strip_legacy_primary_factor_id_and_null_.py`)
  removed the persisted entry→factor denormalization; factors are now derived
  state resolved on demand (`backend/app/services/factor_resolver.py:1-42`).
  The **`DataEntryEmission.primary_factor_id` FK still exists**
  (`backend/app/models/data_entry_emission.py:103-110`, `ondelete=CASCADE`) and is
  written on every emission computation
  (`backend/app/services/data_entry_emission_service.py:497,529`). It is derived
  state too — rebuilt by every recalc.
- **The factor upsert is still live — it was not removed.** Every factor CSV
  upload goes through `FactorRepository.upsert_factors`
  (`backend/app/repositories/factor_repo.py:127-285`): COPY-staged
  `INSERT … ON CONFLICT DO UPDATE` keyed on
  `(data_entry_type_id, year, emission_type_id, classification::text)`, backed by
  two partial unique indexes (`backend/app/models/factor.py:100-125`), invoked
  from `BaseFactorCSVProvider._upsert_batch`
  (`backend/app/services/data_ingestion/base_factor_csv_provider.py:474-495`).
  What 1661 removed is the persisted-`primary_factor_id` _rematch_ inside the
  recalc workflow — likely the source of the "we don't do upsert anymore"
  recollection.

## What a factor CSV re-import does TODAY (current semantics, end to end)

1. Rows are parsed per-row; bad rows (validation error, unresolvable emission
   type) are recorded as row errors and skipped — no crash, no write
   (`base_factor_csv_provider.py:374-393`).
2. Good rows are **upserted in place**: existing identity → `values` +
   `last_seen_job_id` updated, `factor.id` preserved; new identity → inserted
   (`factor_repo.py:41-72`).
3. Only on a 100 % `SUCCESS` run, a **stale sweep** deletes rows for the
   upserted `(det, year)` scope whose `last_seen_job_id` predates this job or is
   NULL (`factor_repo.py:287-324`, gated at `base_factor_csv_provider.py:540-541`).
   Their emission rows go via FK CASCADE.
4. An `emission_recalc` fan-out is chained per affected `(module, det)`
   (`backend/app/tasks/ingestion_tasks.py:120-170`), which rebuilds emissions —
   including `primary_factor_id` — and feeds the stat-bucket aggregation.

**Consequence: the bug reported in #1491 (duplicate factors after a corrected
re-upload) is structurally fixed.** A corrected `SUCCESS` upload replaces
exactly what it carries and sweeps the rest. The specific reproduction (null
`researchfacility_id`) is also closed: those identity fields are required on the
factor DTO (`backend/app/modules/research_facilities/common_schemas.py`), so a
null cell is a per-row error, not a silently-keyed duplicate.

## Is the upsert (id-preservation) still necessary? — the maintainer's actual question

**No longer for correctness; yes for operability. Recommendation: keep it, fix its
documentation.**

- Post-1661 there is **no persisted entry→factor link**, and
  `DataEntryEmission.primary_factor_id` is rebuilt by the recalc that is chained
  after every successful factor ingest. So a delete-all + reinsert ("replace")
  strategy would no longer corrupt anything — the original hard constraint
  (docstring at `factor_repo.py:140-143` still cites the FK as the reason) is
  obsolete as stated.
- But replace-all would be strictly worse operationally:
  - **Partial-upload safety**: today a `WARNING` upload writes what parsed and
    never sweeps — operator error cannot destroy factors. Delete-then-insert has
    no such mode.
  - **Blast radius**: upsert leaves unchanged factors (and their emission rows)
    untouched; replace-all CASCADE-deletes _every_ emission row for the scope
    and leaves reports empty until the chained recalc finishes — or indefinitely
    if it fails.
  - The COPY + ON CONFLICT path is already the performance solution for the
    25k-row purchase files.
- **Action**: keep `upsert_factors`; update the `factor_repo.py:140-143` and
  `base_factor_csv_provider.py:178-181` comments so the stated rationale is
  partial-upload safety + blast radius, with the FK as a secondary
  nice-to-have. Do not build a replace-mode.

## Verdict on the four asks in issue #1491

| #   | Ask (paraphrased)                                                            | Verdict                                                                                                                                                                                                      |
| --- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Explain or change the factor update strategy ("upsert visibly doesn't work") | **Obsolete as a bug** — fixed by 310B upsert + stale sweep + 1661. Residual: write the semantics down (operator-facing), update stale code comments, and decide the one open policy below.                   |
| 2   | Robust error message; don't crash on None classification kind                | **Mostly done** — per-row error capture exists. Residual: one generic null-identity-field guard (below).                                                                                                     |
| 3   | Backoffice viewer for factors per year                                       | **Still open, unchanged** — no such endpoint exists (`backend/app/api/v1/factors.py` has only class-subclass-map + get-by-id; nothing in `backoffice.py`).                                                   |
| 4   | Bulk delete factors/data by entry source                                     | **Still open, unchanged** — plumbing exists internally (`DataEntryService.bulk_delete_by_source`, `data_entry_service.py:365-424`; `data_entry_repo.py:167-209`) but is never exposed; no factor equivalent. |

## Remaining work (small; ordered by value)

### A. One policy decision, then document the semantics (ask 1 residual)

The single unreviewed landmine, still present verbatim
(`factor_repo.py:309-311`): **any factor row not stamped by the current CSV job
is deleted by the next covering upload.** Concretely, the `computed` factor
providers (`backend/app/services/data_ingestion/factor_update_provider.py`)
update factor `values` in place **without** stamping `last_seen_job_id`; their
rows survive only because the CSV re-asserts the same identity (which then
overwrites the computed values). Decide one of:

1. **Accept**: "the factor CSV is the source of truth for its `(det, year)`
   scope; anything else is transient." Then just document it (docs page +
   docstrings) — zero code.
2. **Protect non-CSV rows**: exclude `last_seen_job_id IS NULL` from the sweep
   predicate. One-line change + tests, but re-opens a duplicate-leak path.

Recommendation: option 1 — it matches how the system already behaves and how
operators use it. Either way, add a short "factor lifecycle" section to the docs
describing upsert/sweep/recalc (the issue's ask #1 was literally "mieux
expliquer notre stratégie").

The old plan's second open question (JSON-`::text` identity vs dedicated
columns) is **dropped**: JSONB key-order normalization
(`models/factor.py:26-35`) covers the practical footgun, the identity has two
enforcing unique indexes, and no observed bug remains. Re-open only if a
concrete failure appears.

### B. Null-identity-field guard (ask 2 residual — ~20 lines)

`_process_row` builds `classification` with explicit `None`s for missing fields
(`base_factor_csv_provider.py:354-359`); only per-handler DTO discipline stops a
null from entering the identity key. Add one generic check after the dict is
built: if any `handler.classification_fields` value is `None` **and the handler
does not declare it optional**, record a row error naming the field. Note some
handlers legitimately have nullable classification fields (e.g. subkind-less
rows), so this needs a small per-handler allowlist (e.g. reuse the DTO's
required-field set) rather than a blanket non-null rule. Add a regression test:
CSV row with null identity field → row error, no factor written, upload result
`WARNING`, no sweep.

### C. Backoffice factor viewer (ask 3 — unchanged from previous draft)

- `GET /api/v1/backoffice/factors?data_entry_type_id=&year=` (paginated),
  backed by existing `FactorRepository.list_by_data_entry_type` /
  `count_by_data_entry_type_and_year` (`factor_repo.py:403-465`).
- Serialize via `handler.to_response(factor)`; expose `last_seen_job_id` so an
  operator can spot rows the latest upload didn't assert (this is the
  observability the reporter actually wanted).
- Frontend: extend `frontend/src/stores/factors.ts` / `frontend/src/api/factors.ts`,
  reuse the existing backoffice table pattern.

### D. Bulk delete endpoints (ask 4 — unchanged, plus one new constraint)

- `DELETE /api/v1/backoffice/data-entries?…&source=&year=` wired to the existing
  `DataEntryService.bulk_delete_by_source[_year]`.
- `DELETE /api/v1/backoffice/factors?data_entry_type_id=&year=` via a thin
  `list_id_by_data_entry_type_and_year` + `bulk_delete` composition.
- **New since the stat-bucket refactor (`42186e8c`)**: a manual delete must not
  leave `carbon_report_module.stats` stale. Chain the same recalc fan-out the
  ingest uses, or reuse the admin recompute trigger that already exists —
  `POST /v1/sync/admin/recompute-stats` (`backend/app/api/v1/data_sync.py:2338`,
  commit `0159a4e7`) — scoped to the affected year. Don't ship the delete button
  without one of the two.
- Gate both behind the existing backoffice permission-key scheme.

## Steps

- [x] Decide sweep policy for non-CSV factor writers — **option 1 accepted** (CSV is the source of truth for its scope); satisfied by documentation only, no code change
- [x] Update stale rationale comments (`factor_repo.py`, `base_factor_csv_provider.py`) and add a "factor lifecycle" docs section (`docs/src/backend/12-FACTOR-LIFECYCLE.md`)
- [x] Add generic null-identity-field guard in `_process_row` + regression tests
- [x] `GET /api/v1/backoffice/factors` + frontend viewer (Data Management page section, surfaces `last_seen_job_id`)
- [x] `DELETE /api/v1/backoffice/data-entries` and `DELETE /api/v1/backoffice/factors`, each dispatching an `emission_recalc` (which chains the stat-bucket aggregation); permission-gated; tests
- [ ] ~~Comment on #1491~~ — issue communication is handled by the maintainer; the lifecycle doc and this plan carry the write-up

## Implementation notes (2026-07-10, PR #1744)

- **Sweep policy (ask 1)**: option 1 — the factor CSV is the source of truth
  for its `(det, year)` scope; non-CSV factor writes (computed providers) are
  transient by design. Documented in
  `docs/src/backend/12-FACTOR-LIFECYCLE.md`; no sweep-predicate change.
- **Null-identity guard (ask 2)**: `_process_row` rejects rows whose
  DTO-required classification fields are null, naming the field(s) in the
  per-row error, before emission-type resolution and before the null can
  enter the upsert identity key. Requiredness derives from the handler's
  `required_columns` (create-DTO required set), so legitimately nullable
  classification fields (e.g. subkind) still pass.
- **Recalc vs recompute-stats after bulk delete (ask 4)**: the delete
  endpoints dispatch a root `emission_recalc` job (same shape as
  `POST /sync/recalculate-emissions/{module}/{det}`), NOT the admin
  `recompute-stats` trigger. Reasoning: deleting factors CASCADE-deletes
  the emission rows that reference them, but emission rows with a NULL
  `primary_factor_id` survive with stale values, and surviving data entries
  need their emissions rebuilt — only the recalc path does that (set-based
  replace per entry) and then chains the trailing `aggregation` that
  rewrites `carbon_report_module.stats`. `recompute-stats` only
  re-aggregates existing emission rows (and is designed for unchanged data:
  it skips the module-status bump and skips scopes without a current
  FACTORS job), so it would preserve stale emissions in the stats.
  Module-scoped data-entry deletes pin `carbon_report_module_ids` on the
  recalc config, mirroring the unit-specific ingest.
- **Viewer**: rows serialize through the type's factor handler response DTO
  plus `year` / `last_seen_job_id`;
  `FactorRepository.list_by_data_entry_type` gained an optional
  `limit`/`offset` window (id-ordered). Frontend: a read-only `q-table`
  section on the Data Management page (reuses the page's year selector),
  `listBackofficeFactors` in `api/factors.ts`, `fetchBackofficeFactors` in
  the factors store, en/fr i18n keys.
- **Permissions**: `backoffice.configuration` — `view` for the viewer,
  `edit` for both DELETE endpoints (same gate as the neighbouring
  recalculate/upload operations in `data_sync.py`).
