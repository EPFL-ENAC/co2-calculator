# Bot Review TODOs: PR #998

## Source Branch: `fix/310-poller-auto-recover-stuck-running`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR adds an automatic “pod-crash safety net” to the Plan 310A in-process poller by sweeping for stale RUNNING ingestion jobs and recovering (or terminally failing) them before the usual NOT_STARTED dispatch sweep.

**Changes:**

- Add `DataIngestionRepository.sweep_stuck_running_jobs()` to reset stale RUNNING jobs back to NOT_STARTED (preserving attempts) or mark them FINISHED+ERROR when retries are exhausted.
- Update the safety poller loop to run the new RUNNING-job sweep before dispatching NOT_STARTED jobs.
- Add integration tests covering recovered/abandoned/skip scenarios for the sweep behavior.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated 1 comment.

| File                                                                      | Description                                                                                             |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| backend/app/repositories/data_ingestion.py                                | Implements the sweep that auto-recovers stale RUNNING jobs and abandons those that exceed retry limits. |
| backend/app/tasks/\_poller.py                                             | Invokes the new sweep once per poll tick prior to dispatching NOT_STARTED jobs.                         |
| backend/tests/integration/services/data_ingestion/test_pod_safety_310a.py | Adds integration tests validating sweep behavior across multiple job states and attempt counts.         |

---

### File: `backend/app/repositories/data_ingestion.py` (Line 255) — Copilot

## The sweep treats any RUNNING job with `locked_at` older than `stale_timeout_minutes` as stale, but `locked_at` is only written at claim time (claim_job sets it once) and there’s no heartbeat/refresh during execution. That means any legitimately long-running job (runtime > STALE_JOB_TIMEOUT_MINUTES) will be auto-reset to NOT_STARTED or even marked FINISHED+ERROR while the original pod is still working, which can lead to duplicate processing and inconsistent final state updates. Consider adding a periodic heartbeat that updates `locked_at` (or a separate `last_heartbeat_at`) during job execution, or ensure the staleness check is based on a timestamp that is actively refreshed while the worker is alive.

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/repositories/data_ingestion.py`** (Line 255 — `sweep_stuck_running_jobs`): no heartbeat → a legitimately long-running job (runtime > `STALE_JOB_TIMEOUT_MINUTES`) gets auto-reset to NOT_STARTED while the original pod is still working. The original pod commits its work, the sweep then fires another claim, and a second pod re-runs the same job → **duplicate processing + likely race against the partial-unique-index `is_current` invariant**. Same hazard already exists in the **manual** `recover_job` path, so this PR's auto-trigger doesn't introduce new failure modes — it just exercises them more often. Mitigation paths in priority order:
  1. **Document and pick a generous timeout** (immediate, ~10 min): set `STALE_JOB_TIMEOUT_MINUTES` to ≥ 2× the worst-known job runtime in prod config, document the assumption in the sweep's docstring, and gate the sweep behind a `RUN_BACKGROUND_POLLER`-style toggle so it can be disabled fast if it misfires. No code change to the sweep itself.
  2. **Heartbeat the active worker** (proper fix, ~half-day): add a `last_heartbeat_at TIMESTAMPTZ` column or repurpose `locked_at`; spawn a per-job task that bumps it every N seconds while the worker runs; sweep checks `last_heartbeat_at` instead of `locked_at`. Pairs naturally with Plan 310C's `run_job` runner — that's the right spot to wire the heartbeat. Recommend punting to 310C rather than retrofitting now.
  3. **Worker-side preemption check**: before each commit, the worker re-reads `locked_by` and aborts if it differs from its own `POD_ID`. Cheap defence-in-depth, doesn't replace the heartbeat but limits duplicate-write blast radius if the sweep does misfire. ~1 hour.

### Maintainability / refactoring

- [ ] **`backend/app/repositories/data_ingestion.py`** (`sweep_stuck_running_jobs` docstring): expand the docstring with the heartbeat caveat above so anyone tuning `STALE_JOB_TIMEOUT_MINUTES` sees the long-running-job hazard inline. Cheap, paired with item 1 above.
