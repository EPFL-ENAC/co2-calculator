# Bot Review TODOs: PR #1068

Source Branch: `fix/310-seed-bypass-async-gate`
PR Title: fix(310): seed provider bypasses BULK_PATH_PURE_ASYNC gate [B-H2]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR fixes dev DB seeding under Plan 310-D when `BULK_PATH_PURE_ASYNC=True` by ensuring seed runs do not skip inline emission writes and module stats recomputation (since seed scripts bypass the request-scoped handler chain that would otherwise perform those writes).

**Changes:**

- Bypass the `BULK_PATH_PURE_ASYNC` early-return gates in `BaseCSVProvider` for seed runs via `not getattr(self, "is_seed_run", False)` checks.
- Mark `LocalDataEntryCSVProvider` seed executions with `self.is_seed_run = True` and document why the bypass is required.
- Add focused unit tests covering both seed (bypass) and non-seed (gate remains active) behaviors for both gate sites.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated 2 comments.

| File                                                                                   | Description                                                                                                              |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| backend/app/services/data_ingestion/base_csv_provider.py                               | Makes both async-gate early returns conditional on `not is_seed_run` so seed runs always compute emissions/stats inline. |
| backend/app/services/data_ingestion/csv_providers/local_seed.py                        | Marks `LocalDataEntryCSVProvider` as `is_seed_run=True` and documents the rationale.                                     |
| backend/tests/unit/services/data_ingestion/csv_providers/test_local_seed_async_gate.py | Adds regression tests asserting seed bypass vs non-seed short-circuit under `BULK_PATH_PURE_ASYNC=True`.                 |

---

### File: `backend/tests/unit/services/data_ingestion/csv_providers/test_local_seed_async_gate.py` (Line 68) — Copilot

The comment says an empty `_unit_to_module_map` will trigger a warning and early return _after_ the gate, but the production code only warns/returns when `_unit_to_module_map` is missing or `None`. With `{}`, the method continues (with empty recompute sets). Please update the comment to reflect the actual behavior so the test intent is clear.

---

### File: `backend/tests/unit/services/data_ingestion/csv_providers/test_local_seed_async_gate.py` (Line 90) — Copilot

## This assertion rationale is tied to internal implementation details (service construction) and even references a specific line number in another file ("ran past line 1244"), which is brittle. Consider asserting the gate behavior more directly (e.g., that the gate’s debug log / early-return path is not taken for seed runs, and is taken for non-seed runs).
