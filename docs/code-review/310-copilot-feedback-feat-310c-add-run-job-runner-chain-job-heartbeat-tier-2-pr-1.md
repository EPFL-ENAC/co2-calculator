# Bot Review TODOs: PR #1044

## Source Branch: `feat/310c-runner-runjob-chainjob`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR introduces the Plan 310-C unified job-dispatch infrastructure by adding a single `run_job(job_id)` runner, a `chain_job(...)` helper for parent→child fan-out, and a per-job heartbeat to keep `locked_at` fresh and reduce duplicate-processing risk from stale-job recovery.

**Changes:**

- Added `backend/app/tasks/runner.py` implementing `run_job`, `chain_job`, and `_heartbeat_loop` for unified dispatch, chaining, and lock heartbeats.
- Extended `DataIngestionRepository` with a `heartbeat(job_id, pod_id) -> int` helper to refresh `locked_at` only when the current pod still owns the RUNNING job.
- Added a new unit test suite covering core `run_job`/`chain_job` behavior and preemption semantics.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated 5 comments.

| File                                       | Description                                                                                      |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| backend/app/tasks/runner.py                | Adds unified dispatcher + chaining helper + heartbeat loop for Plan 310-C job execution.         |
| backend/app/repositories/data_ingestion.py | Adds `heartbeat()` to refresh `locked_at` for RUNNING jobs owned by a pod.                       |
| backend/tests/unit/tasks/test_runner.py    | Adds unit coverage for dispatcher guard rails, success/error, preemption, and chaining behavior. |

---

### File: `backend/app/tasks/runner.py` (Line 159) — Copilot

## The handler exception path updates the job to FINISHED+ERROR unconditionally. If the row was preempted mid-run (stale sweep reset + another pod claimed), this will race and can incorrectly finish a job owned by a different pod. Mirror the preemption re-read/locked_by check in the except branch and skip the state update when current.locked_by != POD_ID (or row is missing), after rolling back the data session.

### File: `backend/app/tasks/runner.py` (Line 162) — Copilot

## `fire_and_forget` intentionally logs a warning when a task is cancelled (app/tasks/\_background.py:47-53). Since run_job always cancels the heartbeat task in `finally`, this will emit a warning on every successful job run. Consider running the heartbeat with `asyncio.create_task` (runner holds a strong ref anyway), or add a non-cancelling shutdown mechanism (e.g., an Event) so the task exits cleanly without triggering the cancellation warning.

### File: `backend/app/tasks/runner.py` (Line 122) — Copilot

## After `claim_job` succeeds, the `job` instance fetched before the claim is passed to the handler without a refresh. Because SessionLocal uses `expire_on_commit=False` and `claim_job` uses a SQL UPDATE (not ORM field assignment), the in-memory `job` can still show the pre-claim state (e.g., NOT_STARTED/locked_by=None/attempts not incremented). Re-fetch or `refresh()` the job after claiming so handlers see the authoritative RUNNING row state.

### File: `backend/app/tasks/runner.py` (Line 223) — Copilot

## `chain_job`’s docstring says the child is created with `run_after=now()` but the implementation sets `run_after=None`. Also, the docstring implies the default child is scoped to the parent’s `data_entry_type_id`, but the code leaves `data_entry_type_id` as the explicit arg (default None) rather than inheriting like module/year. Please align the docstring and the actual default inheritance behavior so callers don’t accidentally create unscoped children.

### File: `backend/tests/unit/tasks/test_runner.py` (Line 227) — Copilot

There’s no unit test covering the case where the handler raises _and_ the job is preempted before the runner writes FINISHED+ERROR. Given the success path already has a preemption guard, add a test to ensure the exception path also skips `update_ingestion_job` when `locked_by` no longer matches POD_ID (after rolling back the data session).

---

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/tasks/runner.py` — `run_job` except branch (lines 147-159) is missing the preemption check that the success branch has on lines 127-136.** If a stale-lock sweep preempts the row mid-handler AND the handler then raises, the runner currently writes FINISHED+ERROR over a row a different pod now owns — corrupts the new owner's run. Fix: in the `except Exception` branch, after `data_session.rollback()`, re-read via `repo.get_job_by_id(job_id)` and skip the `update_ingestion_job` + `job_session.commit()` calls when `current is None or current.locked_by != POD_ID`. Cover with the test in the next item below so the regression is pinned.

- [ ] **`backend/app/tasks/runner.py` — `job` instance handed to the handler is stale (line 121).** `claim_job` runs as a raw SQL `UPDATE`, not an ORM mutation, so `job.state`, `job.locked_by`, `job.locked_at`, and `job.attempts` all reflect the _pre-claim_ row. With `expire_on_commit=False` the SQLModel session won't auto-refresh either. Handlers that read `job.attempts` for retry-aware logic, or `job.state` for a sanity assertion, see lies. Fix: after `claim_job` returns True, do `job = await repo.get_job_by_id(job_id)` (which already calls `session.refresh`); the call is cheap and gives handlers the authoritative post-claim row.

- [ ] **`backend/tests/unit/tasks/test_runner.py` — add `test_run_job_handler_raise_with_preemption_skips_state_update`.** Mirrors `test_run_job_preempted_rolls_back_and_skips_state_update` but the handler raises. Asserts: `data_session.rollback()` called, `update_ingestion_job` NOT called when `get_job_by_id` returns a row with `locked_by != POD_ID`. Locks in the fix from the first item above.

### Maintainability / refactoring

- [ ] **`backend/app/tasks/runner.py` — heartbeat is scheduled via `fire_and_forget` (line 114) but always cancelled in `finally` (line 161), which trips `_background._on_done`'s deliberate cancellation `WARNING` on every successful run.** That warning was kept loud for diagnosis after the 310-B fire-and-forget incident; here it would become routine noise and dilute its signal. Fix: switch the heartbeat to plain `asyncio.create_task(_heartbeat_loop(job_id))` (the local `heartbeat_task` variable holds the strong ref while the function runs, so the asyncio-weak-ref hazard `fire_and_forget` exists to fix doesn't apply), and replace `heartbeat_task.cancel()` with `cancel()` + `await heartbeat_task` (swallowing `asyncio.CancelledError`) so cancellation completes deterministically before the function returns. Bot's alternative — Event-based shutdown — works too but adds a second control channel for no extra benefit on this path.

- [ ] **`backend/app/tasks/runner.py` — `chain_job` docstring (lines 181-183) claims `run_after=now()` but the code uses `run_after=None`.** The `None` is correct (claim_job's WHERE treats NULL as eligible — mirrors the existing `ingestion_tasks.py:253` recalc-job creation pattern). Fix: update the docstring to say `run_after=None` ("immediately runnable; claim_job's WHERE treats NULL as eligible"). The bot's secondary claim — that `data_entry_type_id` should also default-inherit from the parent like `module_type_id` and `year` do — is **wrong**; the asymmetry is intentional (a multi-det parent fans out to one child per det, so the caller must pass the specific det per call, mirroring the spec at `docs/src/implementation-plans/310-c-dag-handler-registry.md` lines 240-258). No code change needed there; clarify the docstring with a one-line note explaining the asymmetry.
