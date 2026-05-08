# Bot Review TODOs: PR #1070

Source Branch: `fix/310-recalc-aggregation-on-warning`
PR Title: fix(310): emission_recalc chains aggregation on WARNING [B-C2]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Fixes Plan 310 “emission_recalc” pipeline behavior so aggregation is chained not only on `SUCCESS` but also on `WARNING`, preventing `carbon_reports.stats` from remaining stale when a large recalc completes with partial per-entry failures.

**Changes:**

- Update `emission_recalc_handler` to chain aggregation when `result != ERROR` (so `WARNING` chains too), matching `module_emission_recalc_handler`.
- Update unit coverage to assert aggregation is chained on `WARNING`.
- Add a Postgres integration regression test that verifies the aggregation child job row is persisted (same `pipeline_id`) even when recalc returns `WARNING`.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated no comments.

| File                                                                           | Description                                                                                                                   |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| backend/app/tasks/emission_recalculation_tasks.py                              | Changes the aggregation-chaining gate to include `WARNING` results and documents the contract.                                |
| backend/tests/unit/tasks/test_handler_registrations.py                         | Replaces the prior “skip-on-warning” test with an assertion that chaining occurs on `WARNING` and meta includes the child id. |
| backend/tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py | Adds an end-to-end Postgres regression test ensuring an aggregation child row is created/persisted for `WARNING` recalcs.     |

---
