# Bot Review TODOs: PR #1069

Source Branch: `fix/310-heartbeat-abort-on-failure`
PR Title: fix(310): heartbeat failure aborts handler [B-H3]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR hardens the Plan 310 job runner against prolonged heartbeat (DB) failures by aborting the active handler after sustained heartbeat errors, preventing duplicate work when a stale-lock sweep likely reclaims the job on another pod.

**Changes:**

- Add a shared `abort_event` that `_heartbeat_loop` sets after consecutive heartbeat failures spanning `STALE_JOB_TIMEOUT_MINUTES`, and have `run_job` race handler completion against this event.
- On abort, cancel the handler, roll back `data_session`, and exit without writing `FINISHED`.
- Add targeted unit tests covering the heartbeat failure threshold, counter reset on success, and end-to-end handler cancellation/rollback behavior.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated no comments.

| File                                                    | Description                                                                                                        |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| backend/app/tasks/runner.py                             | Add heartbeat-failure tracking + abort event wiring; `run_job` cancels handler and rolls back when abort triggers. |
| backend/tests/unit/tasks/test_runner.py                 | Update `_heartbeat_loop` test noop to accept the new `abort_event` arg.                                            |
| backend/tests/unit/tasks/test_runner_heartbeat_abort.py | New unit tests for the heartbeat abort threshold and runner-side handler cancellation/rollback.                    |

---
