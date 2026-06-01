# Bot Review TODOs: PR #1020

## Source Branch: `feat/310c-handler-registry`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Introduces the first Plan 310-C slice: a new handler registry module for future unified background-job dispatch, plus unit tests for its basic registration and lookup behavior.

**Changes:**

- Added `app.tasks.registry` with a module-level handler map, `register(job_type)` decorator, `get_handler(job_type)` lookup, and `_reset_registry()` test helper.
- Added unit tests covering successful registration, duplicate registration, unknown lookups, decorator identity, and registry reset behavior.

### Reviewed changes

Copilot reviewed 2 out of 2 changed files in this pull request and generated 2 comments.

| File                                        | Description                                                                                             |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `backend/app/tasks/registry.py`             | Adds the registry scaffolding and public registration/lookup APIs for future job dispatch.              |
| `backend/tests/unit/tasks/test_registry.py` | Adds unit coverage for registry registration, duplicate detection, lookup failures, and reset behavior. |

---

### File: `backend/app/tasks/registry.py` (Line 47) — Copilot

## The decorator currently accepts any callable, so a synchronous function or a function with the wrong parameters can be registered successfully. When Tier 2 starts calling `await handler(job, job_session, data_session)`, that mismatch will only surface as a runtime job failure instead of failing loudly at registration time.

### File: `backend/tests/unit/tasks/test_registry.py` (Line 24) — Copilot

This fixture always leaves the process-wide registry empty after the test. Once real handlers are imported elsewhere in the suite, any later test that expects those import-time registrations will observe a cleared registry, so the suite becomes order-dependent. Restoring the previous registry contents is safer than unconditionally resetting to empty in teardown.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **backend/tests/unit/tasks/test_registry.py**: The teardown fixture unconditionally resets the registry to empty, which will silently clobber any import-time handler registrations once real handlers exist in the suite. Snapshot the registry state in setup and restore it in teardown to avoid order-dependent test failures.

### Maintainability / refactoring

- [ ] **backend/app/tasks/registry.py**: `register(job_type)` accepts any callable, so sync functions or mismatched signatures register silently and only fail at Tier-2 dispatch time. Add a registration-time check (e.g. `inspect.iscoroutinefunction` and signature validation against the future `(job, job_session, data_session)` contract) so misconfigurations fail loudly at import.
