# Bot Review TODOs: PR #1072

Source Branch: `fix/310-finished-cas`
PR Title: fix(310): atomic CAS on FINISHED job-write [B-C1]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR fixes Plan 310 review finding **B-C1** by making the terminal FINISHED write for ingestion jobs an atomic compare-and-set (CAS), preventing a preempted pod from overwriting a newly claimed RUNNING job row.

**Changes:**

- Add `DataIngestionRepository.finish_job(...) -> bool` using `UPDATE ... WHERE id AND locked_by AND state=RUNNING RETURNING ...` to atomically transition to `FINISHED`.
- Update the unified runner to use `finish_job` and to exit cleanly (log + return) if the FINISHED CAS no-ops due to preemption.
- Add/adjust integration + unit tests to simulate and assert the preemption race is handled without clobbering the new owner’s RUNNING row.

### Reviewed changes

Copilot reviewed 4 out of 4 changed files in this pull request and generated 3 comments.

| File                                                                         | Description                                                                                                          |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| backend/app/repositories/data_ingestion.py                                   | Introduces `finish_job` CAS-based terminal transition with idempotent `finished_at` stamping and guarded meta merge. |
| backend/app/tasks/runner.py                                                  | Switches terminal state write to `finish_job` and handles CAS no-op as a clean preemption exit.                      |
| backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py | Adds a real-Postgres regression test covering “late FINISHED write after preemption” behavior.                       |
| backend/tests/unit/tasks/test_runner.py                                      | Updates runner unit tests to assert `finish_job` is used for terminal writes and not called on preemption paths.     |

---

### File: `backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py` (Line 264) — Copilot

## Avoid inline imports in tests as well; move `from sqlalchemy import text` to the module imports to keep import ordering consistent and prevent hidden dependency/circular-import issues.

### File: `backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py` (Line 234) — Copilot

The test docstring’s sequence describes the safety poller sweep recovering the job and then Pod-B claiming with `attempts=2`, but the test uses `recover_job()` (manual recovery), which resets `attempts` to 0 so the subsequent claim yields `attempts==1`. Either update the docstring to reflect `recover_job` semantics, or simulate the poller path using `sweep_stuck_running_jobs` so the narrative matches production behavior.

---

### File: `backend/app/repositories/data_ingestion.py` (Line 163) — Copilot

## The docstring claims meta-merge is safe because “only the lock owner can write meta while it holds the lock”, but `update_ingestion_job()` can still write `meta` without a `(locked_by, state)` guard. Consider tightening the wording to describe the runner’s usage assumptions, or explicitly noting this method is safe against _preemption_ (CAS no-op) but not a general guarantee against arbitrary concurrent meta updates.
