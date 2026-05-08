# Bot Review TODOs: PR #1074

Source Branch: `feat/310-dedup-config`
PR Title: feat(310): chain_job DedupConfig + emission_recalc dedup [#1064]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR generalizes `chain_job`’s deduplication logic from an aggregation-only implementation to a per-job-type `DedupConfig`, and introduces dedup for `emission_recalc` so repeated factor reuploads collapse into a single active recalculation per `(module, det, year)`.

**Changes:**

- Add `DedupConfig` + `AGGREGATION_DEDUP` / `EMISSION_RECALC_DEDUP`, and refactor the dedup insert/pre-check path to be driven by `scope_columns` + `constraint_name` (with a deprecated `dedup_active` shim).
- Add a Postgres partial unique index (`uq_emission_recalc_active`) to enforce active-job deduplication for `emission_recalc`.
- Update chaining call-sites/tests to use `dedup_config=...` and add real-PG integration tests covering the new dedup contract.

### Reviewed changes

Copilot reviewed 6 out of 6 changed files in this pull request and generated 3 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                 | Description                                                                                                    |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| backend/app/tasks/\_chain.py                                                         | Introduces `DedupConfig` and refactors dedup pre-check/INSERT logic; keeps `dedup_active` as a temporary shim. |
| backend/app/tasks/ingestion_tasks.py                                                 | Uses `EMISSION_RECALC_DEDUP` when chaining recalcs for stale factors.                                          |
| backend/app/tasks/emission_recalculation_tasks.py                                    | Migrates aggregation chaining to `dedup_config=AGGREGATION_DEDUP`.                                             |
| backend/alembic/versions/2026_05_07_1432-f8a9b1c2d3e4_emission_recalc_dedup_index.py | Adds the partial unique index for active `emission_recalc` dedup using `CONCURRENTLY`.                         |
| backend/tests/integration/services/data_ingestion/test_emission_recalc_dedup_pg.py   | Adds Postgres integration tests asserting the emission_recalc dedup behavior and invariants.                   |
| backend/tests/unit/tasks/test_handler_registrations.py                               | Updates unit assertions to check `dedup_config` instead of `dedup_active`.                                     |

</details>

---

### File: `backend/app/tasks/_chain.py` (Line 190) — Copilot

## When `dedup_config` is provided, `chain_job` doesn’t validate that `job_type` matches `dedup_config.job_type`. If a caller accidentally passes a mismatched config, the pre-check will query one job_type while the INSERT writes another, silently disabling dedup (and potentially confusing callers). Consider raising a `ValueError` when `job_type != dedup_config.job_type` (and optionally validating `scope_columns` against the supported column set to avoid KeyError/SQL injection via misconfiguration).

### File: `backend/app/tasks/_chain.py` (Line 416) — Copilot

## `_insert_child_with_dedup` catches _any_ `IntegrityError` and treats it as a dedup race-loss. This can mask unrelated integrity failures (e.g., unexpected NOT NULL/enum/foreign-key issues) and cause `chain_job` to silently skip dispatching work. Consider narrowing the handler to only swallow unique-violation errors for `dedup_config.constraint_name` (and re-raise anything else).

### File: `backend/tests/integration/services/data_ingestion/test_emission_recalc_dedup_pg.py` (Line 320) — Copilot

This test creates an async SQLAlchemy engine but never disposes it, unlike the other tests in this file. Add `await engine.dispose()` at the end to avoid leaking connections across the integration test suite.

---
