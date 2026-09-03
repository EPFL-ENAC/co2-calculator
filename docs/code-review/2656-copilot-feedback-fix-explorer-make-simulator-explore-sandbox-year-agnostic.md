# Bot Review TODOs: PR #2657

Source Branch: `fix/2656-explorer-year-agnostic-sandbox`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (enac-ai-reviewer)

This PR makes the Explorer sandbox year-agnostic by removing the year key from the explore endpoint, always creating a fresh sandbox on POST, and cleaning up older sandboxes in a background task. The change also makes factor resolution use the latest started year instead of the sandbox's own year, and drops the per-creator unique index. Overall the design is sound, but there are a few areas worth scrutinizing: the background cleanup task's error handling, the race between concurrent creates and cleanup, and the factor-year fallback logic.
---

### File: `backend/app/api/v1/carbon_report.py` (Line 40) — enac-ai-reviewer[bot]

The background cleanup task opens its own session and calls delete_old_explore, but there's no try/except around it. If the background task raises (e.g. a DB error), FastAPI's BackgroundTasks will swallow the exception and log it, but the user's older sandboxes will never be cleaned up, silently accumulating. Consider wrapping in try/except and logging, or at least noting this is intentional.
---

### File: `backend/app/repositories/carbon_report_repo.py` (Line 200) — enac-ai-reviewer[bot]

list_explore_by_unit_older_than selects reports strictly older than keep_project_id by project id. But the cleanup task runs in the background after the response is sent, and a concurrent 'start exploration' POST could create a new project with a higher id between the create and the cleanup. Since the filter is `project.id < keep_project_id`, the newer concurrent project is correctly excluded — good. However, the cleanup deletes reports by project id, and if the concurrently-created project's reports are also deleted by this task (they aren't, since they're newer), there'd be a race. This looks correct, but worth a test to confirm the double-click race is covered.
---

### File: `backend/app/api/v1/carbon_report.py` (Line 158) — enac-ai-reviewer[bot]

The POST now always creates a new sandbox and returns 201. But the GET route (line ~121) returns 404 if no sandbox exists. The frontend previously used GET(404) + POST orchestration; now the flow is POST to create then GET to read. If the frontend still calls GET first on page mount expecting a create-fallback, it will get a 404. Verify the frontend was updated to always POST first, otherwise existing clients will break.
---

### File: `backend/app/api/v1/carbon_report.py` (Line 160) — enac-ai-reviewer[bot]

The create endpoint checks `result.carbon_project_id is None` and raises 500. But ExploreProvisioningWorkflow.create presumably commits the project creation. If the 500 is raised after the project was already created/committed, the caller's new sandbox exists but the response is an error, and no cleanup task is scheduled — leaving an orphaned sandbox. Consider whether the create should be transactional with the error check.
---

## Action Items

### Critical: logic, security, correctness

- [x] **`backend/app/api/v1/carbon_report.py`** — `_cleanup_old_explore_background` had no error handling: `delete_old_explore` + `db.commit()` ran unguarded, so a DB error (or any exception) during background cleanup silently left the caller's older Explore sandboxes undeleted with no log trail. Fixed: wrapped the body in `try/except Exception` + `logger.error(..., exc_info=True)`, mirroring `backend/app/tasks/audit_sync_tasks.py`'s convention — caught, logged with `unit_id`/`created_by`/`keep_project_id` context, not re-raised (the response is already sent).

### Dropped after verification (one revised)

- **Race-condition test coverage for `list_explore_by_unit_older_than`** (repo, "Line 200") — the bot concluded the filter is correct and asked for a test confirming it; the one test that existed only proved the _safe_ half (an older cleanup never deletes a newer create). It missed the direction that actually deletes something live: the _newest_ create's cleanup deletes the _older_ concurrent create's own project — so a two-tab race has exactly one survivor (the newest), not two, and the earlier tab's active sandbox is gone. Not a bug — this matches the already-accepted "reload always loses your sandbox" design, just applied to two concurrent creates instead of one reload — but the plan doc claimed "two survivors" and the test suite only pinned the harmless direction. Fixed: added `test_delete_old_explore_deletes_an_older_concurrent_create` (mirrors the existing test, opposite direction) and corrected the plan doc's race description. **Verdict: partial** — behavior is intentional and needed no code change, but the documentation and test coverage were wrong/incomplete and are now fixed.
- **Frontend still calling GET-then-create-fallback** (route, "Line 158") — verified against `frontend/src/stores/workspace.ts#selectSimulatorExploreCarbonReport`: it calls `postExploreCarbonReport` (POST) directly and unconditionally on every page mount/refresh; there is no GET-first branch anywhere in this PR's frontend diff. **Verdict: wrong** — the scenario the bot warns about doesn't exist in the shipped code.
- **500-after-commit leaves an orphaned, uncleaned sandbox** (route, "Line 160") — traced the sequence: `ExploreProvisioningWorkflow.create()` sets `carbon_project_id` from the freshly-flushed `CarbonProject.id` _within the same transaction_ it then commits, so by the time the route's `if result.carbon_project_id is None` guard runs, the value has already been proven non-null moments earlier — there is no code path that reaches that branch. It's a type-narrowing guard for the `int | None` schema field, matching the codebase's existing idiom (e.g. `if current_user.id is None: raise ...` a few lines above in the same file), not a reachable failure mode. **Verdict: wrong** — no live gap to fix.

### Considered and rejected: cancellable "delete pipeline"

Proposed alternative to the id-based cleanup: model cleanup as a
cancellable pipeline job, where a new "start exploration" cancels the
previous cleanup and starts a new one. Rejected — it targets the wrong
half of the race. In the two-create scenario above, cancellation would
cancel the _earlier_ tab's cleanup (`keep=first`, which only deletes
things older than `first` — the harmless one) while the _later_ tab's
cleanup (`keep=second`, the one that deletes `first`) is what's actually
destructive, and it's the one still running unopposed. The mechanism
would add a cancellation channel, a job/task registry, and idempotent
resumable delete units — real complexity — without changing the
user-visible outcome at all. It also routes a disposable scratch-sandbox
cleanup through the project's job/pipeline machinery, which the
guardrails explicitly fence off ("do not touch pipeline internals without
a written plan reviewed by both maintainers"). If two tabs coexisting
ever becomes a real requirement, the cheap lever is the delete predicate
(e.g. skip projects whose report has a recent `last_updated`), not a
cancellation channel — no new infrastructure needed.
