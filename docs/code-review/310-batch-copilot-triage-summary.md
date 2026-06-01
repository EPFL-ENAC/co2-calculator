---
status: review
issue: 310
last_updated: 2026-05-07
title: "310 — Batch Copilot Triage Summary (PRs #1068-#1078)"
summary: "Consolidated triage of Copilot reviews on the 11 batch PRs against feat/310/dev. Verdict + actionable items per PR."
---

# 310 Batch — Copilot Triage Summary

11 PRs reviewed by Copilot on `feat/310/dev`. Detailed per-PR feedback in
`docs/code-review/310-copilot-feedback-*.md`. Verdicts below were triaged
against the actual code; nitpicks dropped, verified bugs surfaced.

## Per-PR verdict

| PR    | Title                    | Copilot comments | Verified bugs | Nits/maintainability                    |
| ----- | ------------------------ | ---------------- | ------------- | --------------------------------------- |
| #1072 | B-C1 atomic CAS          | 3                | 0             | 3 (docstring + test narrative)          |
| #1070 | B-C2 chain on WARNING    | 0                | 0             | —                                       |
| #1071 | F-C1 a11y tooltip focus  | 0                | 0             | —                                       |
| #1076 | B-H1 kg_co2eq carrier    | 5                | **1**         | 4 (test constants, docstring)           |
| #1068 | B-H2 seed bypass         | 2                | 0             | 2 (test docstring)                      |
| #1069 | B-H3 heartbeat abort     | 0                | 0             | —                                       |
| #1078 | A-H1/H2/H3 SSE           | 0                | 0             | —                                       |
| #1073 | M-H2 index doc + logging | 0                | 0             | —                                       |
| #1074 | #1064 DedupConfig        | 3                | **2**         | 1 (test cleanup)                        |
| #1077 | #1063 stale-stats        | 2                | 0             | 2 (docstring path, plan PR placeholder) |
| #1075 | #1062 unified store      | 1                | **1**         | —                                       |

**4 verified bugs across 3 PRs. 8 PRs are clean or have only nits.**

## Verified bugs — must fix before merging to `dev`

### V1 — PR #1075: duplicate `/v1` prefix breaks `/sync/active-pipelines` endpoint

**File**: `frontend/src/stores/pipelineState.ts:75`
**Severity**: Critical (the new unified store endpoint is unreachable).
The frontend `api` client is configured with `prefixUrl: '/api/v1/'`. The
store calls `api.get('v1/sync/active-pipelines?...')` which produces
`/api/v1/v1/sync/active-pipelines` — a 404. Frontend's "Recalculating…"
badge will never populate via the new store.
**Fix**: drop the `v1/` prefix in the store call: `api.get('sync/active-pipelines', { searchParams })`.

### V2 — PR #1076: `or` short-circuit drops `kg_co2eq=0` overrides

**File**: `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py:431` (and the parallel `distance_km` line)
**Severity**: High (silent data corruption for zero-emission travel rows; e.g., walking, fully electric trips on green grids).
Code is `kg_co2eq = item.get("kg_co2eq") or item.get("OUT_CO2_CORRECTED")`.
A valid `0` / `0.0` falls through and either picks up `OUT_CO2_CORRECTED`
or becomes `None`. Same shape on `distance_km`.
**Fix**: explicit `is not None` checks:

```python
v = item.get("kg_co2eq")
kg_co2eq = v if v is not None else item.get("OUT_CO2_CORRECTED")
```

### V3 — PR #1074: `chain_job` doesn't validate `job_type == dedup_config.job_type`

**File**: `backend/app/tasks/_chain.py:190`
**Severity**: High (silent dedup bypass on misconfiguration).
A caller passing `job_type='aggregation'` with `dedup_config=EMISSION_RECALC_DEDUP`
would have the pre-check query one job_type while the INSERT writes
another. Dedup silently disabled. Future second-consumer of the
generalized API is the most likely victim.
**Fix**: at the top of `chain_job` when `dedup_config is not None`:

```python
if job_type != dedup_config.job_type:
    raise ValueError(
        f"chain_job: job_type={job_type!r} does not match "
        f"dedup_config.job_type={dedup_config.job_type!r}"
    )
```

### V4 — PR #1074: `_insert_child_with_dedup` swallows ALL `IntegrityError`

**File**: `backend/app/tasks/_chain.py:416`
**Severity**: Medium-High (hides unrelated integrity violations).
Catching any `IntegrityError` and treating it as a dedup race-loss masks
NOT NULL / FK / enum violations and silently skips dispatching work.
**Fix**: narrow the catch to only the configured constraint:

```python
except IntegrityError as exc:
    msg = str(getattr(exc.orig, "diag", None) or exc)
    if dedup_config.constraint_name in msg:
        return existing_id_lookup_or_none()
    raise
```

Test: add a unit test that injects a non-dedup IntegrityError and asserts it propagates.

## Maintainability / nits (not blockers)

These don't block merge but are worth folding into a single follow-up cleanup PR after the batch:

- **PR #1072**: `from sqlalchemy import text` should be moved to module-level imports in the new test; finish_job docstring should specify "safe against preemption (CAS no-op), not a general guard against arbitrary concurrent meta updates"; test docstring narrative says "attempts=2" but `recover_job` resets to 0, so the actual claim yields `attempts=1`.
- **PR #1076**: 3 test files hardcode the literal `"__kg_co2eq_override__"`; should import `KG_CO2EQ_OVERRIDE_KEY`. The `_process_row` docstring still claims kg_co2eq_override is carried out-of-band — needs updating.
- **PR #1068**: test docstring at L68 says empty `_unit_to_module_map` triggers warning + early return (it doesn't with `{}`); test at L90 references a brittle "ran past line 1244" rationale.
- **PR #1074**: `test_emission_recalc_dedup_pg.py:320` creates an async engine without `await engine.dispose()` — connection leak in test suite.
- **PR #1077**: `StaleStatsEntry` docstring says `GET /sync/health/stale-stats` but the actual path is `/v1/sync/health/stale-stats`. Plan doc `310-d-architecture-followups.md:26` still has `PR #<TBD>` placeholder; replace with #1077.

## Recommended ordering for follow-up

1. **Land V1 (PR #1075)** first — the unified-store deliverable is unusable without it. Single-line fix on the existing branch.
2. **Land V2 (PR #1076)** — silent data corruption on zero-valued overrides.
3. **Land V3 + V4 (PR #1074)** together — both touch `_chain.py`. Single follow-up commit on the existing branch.
4. **Bundle nits** into one cleanup PR after the batch merges to `feat/310/dev`.

## Clean PRs ready to merge as-is

#1070 (B-C2), #1071 (F-C1), #1069 (B-H3), #1078 (SSE), #1073 (index doc + logging) — Copilot found nothing. The Critical/High findings on these areas are addressed cleanly.
