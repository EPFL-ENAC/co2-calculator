# Copilot Review TODOs: PR #956

## Source Branch: `feat/310-backoffice-recalculation-upon-factors-update`

## Raw Feedback

### Summary Feedback

## Pull request overview

This PR starts implementing the “Plan 310” background-job safety architecture for the bulk/backoffice path: adding atomic job claiming, a safety poller to recover orphaned jobs, and a manual job recovery endpoint, alongside detailed implementation plan docs.

**Changes:**

- Add Plan 310A job-claiming fields to `DataIngestionJob`, plus repository helpers (`claim_job`, `recover_job`, pending-jobs query) and DB migrations.
- Introduce an in-process poller started from FastAPI lifespan, and update ingestion/recalculation tasks to `claim_job` before executing.
- Add docs for plans 310a–310d and add/update unit + integration tests around claiming/recovery behavior.

### Reviewed changes

Copilot reviewed 23 out of 23 changed files in this pull request and generated 8 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                                               | Description                                                                      |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| docs/src/database/erd.md                                                                                           | Updates ERD to reflect new ingestion-job fields and user roles sync timestamp.   |
| docs/implementation-plans/310a-pod-safety.md                                                                       | Plan doc for atomic claim, poller, and recovery endpoint.                        |
| docs/implementation-plans/310b-factor-pipeline.md                                                                  | Plan doc for factor upsert pipeline and unit-sync tracking.                      |
| docs/implementation-plans/310c-dag-handler-registry.md                                                             | Plan doc for handler registry + unified runner.                                  |
| docs/implementation-plans/310d-pipeline-responsibility-split.md                                                    | Plan doc for splitting bulk path into ingest → recalc → aggregation.             |
| docs/implementation-plans/310-overview.md                                                                          | High-level architecture and decisions across plans A–D.                          |
| docs/implementation-plans/310-review.md                                                                            | Review notes identifying showstoppers and plan corrections.                      |
| docs/implementation-plans/310-backoffice-recalculation-upon-factors-update.md                                      | Additional implementation-plan notes (currently transcript-like).                |
| backend/app/models/data_ingestion.py                                                                               | Adds locked/attempts/run_after/pipeline_id/job_type fields + pending-jobs index. |
| backend/app/repositories/data_ingestion.py                                                                         | Implements `claim_job`, `recover_job`, and poller query helper.                  |
| backend/app/tasks/\_pod_id.py                                                                                      | Introduces per-pod identity constant for locking.                                |
| backend/app/tasks/\_poller.py                                                                                      | Adds in-process poller and dispatch logic for orphaned jobs.                     |
| backend/app/tasks/ingestion_tasks.py                                                                               | Adds `claim_job` guard before provider ingestion runs.                           |
| backend/app/tasks/emission_recalculation_tasks.py                                                                  | Adds `claim_job` guard and removes direct RUNNING-state flip.                    |
| backend/app/main.py                                                                                                | Starts/cancels the safety poller in FastAPI lifespan.                            |
| backend/app/core/config.py                                                                                         | Adds settings for stale-timeout and enabling/disabling the poller.               |
| backend/app/api/v1/data_sync.py                                                                                    | Extends job response fields; adds `/sync/jobs/{job_id}/recover` endpoint.        |
| backend/tests/conftest.py                                                                                          | Disables poller globally in tests (autouse fixture).                             |
| backend/tests/unit/services/data_ingestion/test_background_tasks.py                                                | Updates unit tests to mock `claim_job`.                                          |
| backend/tests/unit/tasks/test_emission_recalculation_tasks.py                                                      | Updates unit tests to mock `claim_job`; adjusts expectations.                    |
| backend/tests/integration/services/data_ingestion/test_pod_safety_310a.py                                          | Adds integration tests around claim/recover/poller behavior (SQLite-backed).     |
| backend/alembic/versions/2026_04_29_1000-a1b2c3d4e5f8_add_claiming_retry_grouping_fields_to_data_ingestion_jobs.py | Migration adding new claiming/retry/grouping fields + pending index.             |
| backend/alembic/versions/2026_04_30_1445-068a0db9176b_forgotten_migration.py                                       | Migration adding `data_entry_emissions.scope` column.                            |

</details>

---

### Summary Feedback

## Pull request overview

Copilot reviewed 22 out of 22 changed files in this pull request and generated 7 comments.

<details>
<summary>Comments suppressed due to low confidence (1)</summary>

**backend/app/tasks/ingestion_tasks.py:43**

- `run_sync_task` calls `claim_job` before validating that the job exists and that `provider_class_name` resolves to a provider. If `get_job_by_id` returns None or `ProviderFactory.get_provider_class(...)` returns None, the function returns early after the job was already claimed (state=RUNNING, locked_by set), leaving the job stuck in RUNNING until manual recovery. Handle these error branches by updating the job to FINISHED/ERROR (and clearing is_current/lock as appropriate), or move the claim after the basic validation steps.

```
        claimed = await job_repo.claim_job(job_id, POD_ID)
        if not claimed:
            logger.info(f"Job {job_id} already claimed or not eligible — skipping")
            return

        # Retrieve job from db
        job = await job_repo.get_job_by_id(job_id)
        if not job:
            logger.error(f"Job ID {job_id} not found.")
            return
        provider_class = ProviderFactory.get_provider_class(provider_class_name)
        if not provider_class:
            logger.error(f"Provider class '{provider_class_name}' not found.")
            return
```

</details>

---

### Summary Feedback

## Pull request overview

Copilot reviewed 24 out of 24 changed files in this pull request and generated 8 comments.

---

### Summary Feedback

## Pull request overview

Copilot reviewed 25 out of 25 changed files in this pull request and generated 2 comments.

---

### File: `backend/app/tasks/emission_recalculation_tasks.py` (Line 71)

This `update_ingestion_job(...)` call no longer passes `state=IngestionState.RUNNING`. With the current repository implementation, passing `state=None` can overwrite the job's state to NULL, undoing the RUNNING state set by `claim_job()` and breaking job tracking/SSE. Pass `state=IngestionState.RUNNING` here (and/or adjust the repository update helper to avoid overwriting when state is None).

```suggestion
                metadata={},
                state=IngestionState.RUNNING,
```

---

### File: `backend/app/tasks/emission_recalculation_tasks.py` (Line 187)

Same issue as the single-type variant: this progress `update_ingestion_job(...)` call omits `state=IngestionState.RUNNING`, which can clear the job state back to NULL after a successful `claim_job()`. Pass `state=IngestionState.RUNNING` for these progress updates (and/or fix the repository helper to not overwrite state/result when None).

```suggestion
                    metadata={},
                    state=IngestionState.RUNNING,
```

---

### File: `backend/app/tasks/_poller.py` (Line 61)

## `dispatch_job()` assumes ingestion jobs have `meta.provider_name`/`meta.filters`, but current job creation paths (e.g. `DataIngestionProvider.create_job` and the recalc endpoints) don’t persist those fields and also don’t set `job_type`. As a result, the poller will keep selecting orphan NOT_STARTED jobs and then skip them, so the “orphan recovery” mechanism won’t actually recover most real jobs. Either persist `provider_name`/`filters` (and set `job_type`) when creating jobs, or make the dispatcher derive the correct handler from existing job fields (target_type/ingestion_method/meta.config).

### File: `backend/app/api/v1/data_sync.py` (Line null)

## Avoid inline imports inside request handlers. Import `get_settings` at module scope (or reuse a module-level `settings = get_settings()` like other API modules) to keep imports consistent and avoid hiding circular-dependency issues.

### File: `backend/tests/integration/services/data_ingestion/test_pod_safety_310a.py` (Line null)

## These tests run against the repo’s in-memory SQLite test DB (see `backend/tests/conftest.py`), so they can’t validate the Postgres-specific behavior this change relies on (partial unique indexes and the IntegrityError path on concurrent claims). Consider running this file against a real Postgres instance in CI (or clearly marking/skipping the concurrency-specific assertions) so we actually prove the multi-pod safety mechanism works under contention.

### File: `docs/implementation-plans/310-backoffice-recalculation-upon-factors-update.md` (Line null)

This doc reads like a chat transcript (e.g. “Got it — …”) and uses emoji-heavy headings, which makes it inconsistent with the other implementation-plan docs in this PR. It also mixes guidance that doesn’t match the current codebase direction (e.g. orchestration statements), which can confuse future readers. Consider rewriting it into the same structured format as the 310a–310d plans (title, context, decisions, steps, tests), or removing it if it’s redundant with the other plan files.

```suggestion
# 310 Backoffice recalculation upon factors update

## Context

This plan covers how the backoffice should trigger recalculation when emission factors change. The goal is to keep derived emissions and report aggregates consistent with the latest factor data while avoiding duplicate writes and unclear ownership between processing stages.

## Decisions

- Recalculation is treated as a backend-controlled process for refreshing derived data after factor updates.
- Processing stages remain explicit and aligned to the current data model:
  - ingestion writes `data_entries`
  - computation rebuilds `data_entry_emissions`
  - aggregation refreshes `carbon_reports`
- `carbon_reports` remains the single aggregate write target.
- Recalculation operations must be idempotent so retries do not create duplicate derived rows.
- Aggregate writes should use update semantics so refreshed values replace outdated totals.

## Implementation steps

### 1. Identify impacted records

- Determine which entries, emissions, and reports are affected by a factor update.
- Scope recalculation to impacted data instead of recomputing unrelated records.

### 2. Rebuild derived emissions

- Recompute `data_entry_emissions` from `data_entries` using the updated factors.
- Keep the computation stage responsible only for derived emission values.

### 3. Refresh report aggregates

- Recalculate `carbon_reports` from the latest derived emissions.
- Keep aggregation as the only writer for report-level totals.
- Use deterministic update behavior for existing aggregate rows.

## Tests

- Factor update recalculates impacted `data_entry_emissions`.
- Factor update refreshes affected `carbon_reports`.
- Re-running recalculation produces the same final state.
- Unaffected records remain unchanged.
- Partial failures do not leave aggregate data in a mixed old/new state.
- Multi-record updates and repeated updates preserve data consistency.
```

---

### File: `backend/app/repositories/data_ingestion.py` (Line null)

## `claim_job()` unsets `is_current` for the existing job in the same combo unconditionally. If a job is already RUNNING/current, this allows a second job for the same (module_type_id, data_entry_type_id, target_type, ingestion_method, year) to be claimed and run concurrently (because the unique index no longer blocks after the unset). Consider only unsetting `is_current` for FINISHED jobs (or otherwise refusing the claim when another RUNNING job exists for the combo).

### File: `backend/app/repositories/data_ingestion.py` (Line 186)

`claim_job()` doesn't currently gate on `run_after`, so callers can claim and execute jobs that are scheduled for the future (or intended to be delayed for retry/backoff). Add a WHERE condition like `(run_after IS NULL OR run_after <= now())` to enforce scheduling consistently (similar to `_pending_jobs_query`).

```suggestion
                    col(DataIngestionJob.attempts) < col(DataIngestionJob.max_attempts),
                    or_(
                        col(DataIngestionJob.run_after).is_(None),
                        col(DataIngestionJob.run_after) <= func.now(),
                    ),
```

---

### File: `backend/alembic/versions/2026_05_01_1048-e528e0d649cd_add_new_information_for_jobs.py` (Line 47)

## Alembic adds NOT NULL columns `attempts` and `max_attempts` without a `server_default`/backfill. On a non-empty `data_ingestion_jobs` table, this migration will fail because existing rows cannot satisfy the NOT NULL constraint. Add a temporary server_default (e.g., 0 and 3) or a data backfill step before making them NOT NULL, and (optionally) drop the default afterward.

### File: `backend/alembic/versions/2026_05_01_1048-e528e0d649cd_add_new_information_for_jobs.py` (Line null)

## This migration includes an unrelated `alter_column` on `data_entry_emissions.additional_value` (comment changes) which is not part of the job-safety feature. Keeping migrations tightly scoped reduces review/deploy risk; please remove this unrelated DDL change (or move it to a dedicated migration/PR).

### File: `docs/implementation-plans/310a-pod-safety.md` (Line null)

## This implementation plan filename doesn’t match the repository convention used for implementation plans (issue-id as an integer followed by a dash, e.g. `docs/implementation-plans/220-csv-upload-implementation-summary.md`). Please rename this file to start with `310-...` (for example `310-a-pod-safety.md` or similar) so it’s discoverable and consistent.

### File: `docs/implementation-plans/310b-factor-pipeline.md` (Line null)

## This implementation plan filename doesn’t match the repository convention used for implementation plans (issue-id as an integer followed by a dash, e.g. `docs/implementation-plans/220-csv-upload-implementation-summary.md`). Please rename this file to start with `310-...` (for example `310-b-factor-pipeline.md` or similar) so it’s discoverable and consistent.

### File: `docs/implementation-plans/310d-pipeline-responsibility-split.md` (Line null)

## This implementation plan filename doesn’t match the repository convention used for implementation plans (issue-id as an integer followed by a dash, e.g. `docs/implementation-plans/220-csv-upload-implementation-summary.md`). Please rename this file to start with `310-...` (for example `310-d-pipeline-responsibility-split.md` or similar) so it’s discoverable and consistent.

### File: `backend/tests/integration/services/data_ingestion/test_pod_safety_310a.py` (Line null)

## This test is named as if it verifies the "unset previous is_current for the same combo" behavior, but `old_job` and `new_job` are created with different `ingestion_method` and different `data_entry_type_id`, so they are not the same combo and the unset step is never exercised. Consider setting `old_job` to the same (module_type_id, data_entry_type_id, target_type, ingestion_method, year) as `new_job` (with `is_current=True`) and assert `old_job.is_current` becomes False after claiming `new_job`.

### File: `docs/implementation-plans/310c-dag-handler-registry.md` (Line null)

## This implementation plan filename doesn’t match the repository convention used for implementation plans (issue-id as an integer followed by a dash, e.g. `docs/implementation-plans/220-csv-upload-implementation-summary.md`). Please rename this file to start with `310-...` (for example `310-c-dag-handler-registry.md` or similar) so it’s discoverable and consistent.

### File: `backend/tests/unit/tasks/test_emission_recalculation_tasks.py` (Line 224)

## This test sets `claim_job()` to True while `get_job_by_id()` returns None. In the real repository implementation, `claim_job()` looks up the job and returns False if it doesn’t exist, so this path isn’t representative. Consider updating the test to assert the early-return behavior when `claim_job=False` for a missing job id, or refactor the task to fetch the job before claiming.

### File: `backend/app/tasks/emission_recalculation_tasks.py` (Line 63)

Same pattern as ingestion: `run_recalculation_task` claims before loading the job. With the real repo, a missing job yields `claim_job=False`, so the “job not found” branch won’t run and logs will be misleading. Fetch the job first or make `claim_job` provide a distinct not-found signal.

```suggestion
        job = await job_repo.get_job_by_id(job_id)
        if not job:
            logger.error(f"Recalculation job {job_id} not found.")
            return

        claimed = await job_repo.claim_job(job_id, POD_ID)
        if not claimed:
            logger.info(f"Job {job_id} already claimed or not eligible — skipping")
            return
```

---

### File: `backend/app/api/v1/data_sync.py` (Line 806)

`DataIngestionRepository.recover_job()` already commits the session internally; this endpoint then commits again. Either remove the extra `await db.commit()` here, or (preferably) move commit control out of the repository method so transaction boundaries are consistent (repo = build statements, caller = commit/rollback).

```suggestion

```

---

### File: `backend/app/repositories/data_ingestion.py` (Line null)

## `claim_job()` clears any existing `is_current` row for the combo before it knows the target job can be claimed. If there is a RUNNING current job for that combo, a concurrent claim of a sibling job can flip the RUNNING job’s `is_current` to FALSE and then successfully claim the sibling, resulting in multiple RUNNING jobs for the same combo (the original job keeps running; nothing cancels it). Consider restricting Step 1 to only clear previous rows that are not RUNNING (and/or whose lock is stale), so that an active RUNNING job blocks new claims via the partial unique index.

### File: `backend/app/repositories/data_ingestion.py` (Line 202)

`claim_job()` commits even when the Step 2 UPDATE affects 0 rows (job already locked/finished/max_attempts/etc.). Because Step 1 already executed, this can permanently clear the previous `is_current` row even though no claim happened. Wrap both steps in a transaction and only commit when the claim succeeds; otherwise rollback so `is_current` doesn’t get cleared on failed claims.

```suggestion
            claimed_id = result.scalar_one_or_none()
            if claimed_id is None:
                await self.session.rollback()
                return False

            await self.session.commit()
            return True
```

---

### File: `backend/app/tasks/ingestion_tasks.py` (Line 43)

## `run_sync_task` calls `claim_job()` before loading the job. Since `claim_job()` returns False when the job doesn’t exist, missing-job cases will be logged as “already claimed / not eligible” and the later “Job ID … not found” branch is effectively unreachable with the real repository implementation. Consider fetching the job first (to log not-found clearly) and/or changing `claim_job` to return a richer status so callers can distinguish not-found vs already-claimed.

### File: `backend/app/main.py` (Line 73)

There’s a stray standalone string literal inside the `lifespan()` function body (`"""Run on application shutdown."""`). It’s a no-op expression and likely accidental; please remove it to avoid confusing readers and linters.

```suggestion

```

---

### File: `backend/tests/unit/services/data_ingestion/test_background_tasks.py` (Line 92)

## These unit tests force `claim_job()` to return True even when `get_job_by_id()` returns None. With the real repository, `claim_job()` returns False for missing jobs, so this scenario can’t occur. Either refactor the task to load the job before claiming (so “not found” remains reachable) or update the tests to cover the realistic behavior (`claim_job=False` → early return).

### File: `backend/app/tasks/_poller.py` (Line 54)

## The safety poller will repeatedly pick up NOT_STARTED jobs with job_type=None (current default) and then skip them because meta['provider_name'] is missing. This means orphan recovery does not actually work for the majority of jobs created by the API/provider flows, and can also cause log spam every poll interval. Consider (1) populating job_type (and provider_name for ingest) at job creation time, and (2) having the poller query/dispatch only jobs it can actually run (e.g., filter job_type IS NOT NULL) until the unified runner lands.

### File: `backend/app/tasks/emission_recalculation_tasks.py` (Line 165)

## run_module_recalculation_task now uses claim_job() (which relies on is_current for exclusivity), but later in this workflow per-type stub jobs are marked current via mark_job_as_current(). mark_job_as_current() can demote an already-RUNNING sibling job for the same combo, which re-opens the window for concurrent claims (RUNNING rows with is_current=False). To keep the new atomic-claim design sound, ensure the remaining is_current updates cannot demote RUNNING siblings (or stop marking these stub jobs as current).

## Action Items

> **Verification context**: every comment below was checked against current code (post-commit `2841d40a`). The fix-up commit already addressed most of Copilot's substantive items: `claim_job` RUNNING-sibling race, `run_after` gate, `update_ingestion_job` null-state clobber, migration NOT-NULL defaults, the unrelated migration column, plan-doc filenames, the chat-transcript plan rewrite, real-Postgres concurrency tests, and the ingestion-task claim-before-validate ordering. Those are not listed here.

### Critical: logic, security, correctness

- [ ] **backend/app/repositories/data_ingestion.py** — `claim_job()` Step 1 demote is committed even when Step 2 silently matches 0 rows (e.g. `attempts >= max_attempts`, `run_after` in the future), leaving the prior FINISHED `is_current` row demoted with nothing taking its place. The IntegrityError path already rollbacks correctly, so the leak is only on the silent-zero path. Fix: after the Step 2 `UPDATE … RETURNING`, branch on `scalar_one_or_none()` — `await rollback()` and return False when None; commit and return True otherwise.

### Maintainability / refactoring

- [ ] **backend/app/repositories/data_ingestion.py** + **backend/app/api/v1/data_sync.py:806** — `recover_job()` commits internally (line 236), then the endpoint commits the same session again. Pick one transaction owner. Recommended: drop `await db.commit()` from the endpoint, since the rest of the repo also self-commits and changing repo conventions is out of scope here.
- [ ] **backend/app/repositories/data_ingestion.py:333** — `mark_job_as_current()` lacks the `state != RUNNING` guard that `claim_job()` got. No current caller hits a same-combo RUNNING sibling (module-job uses `data_entry_type_id=None`, stub jobs use real ids), but the asymmetry will bite Plan B/D when more code paths touch `is_current`. Fix: add `col(state) != IngestionState.RUNNING` to the unset WHERE clause to match `claim_job`'s invariant.
- [ ] **backend/app/main.py:73** — stray `"""Run on application shutdown."""` expression-statement inside the lifespan body. Delete the line.
- [ ] **backend/app/tasks/emission_recalculation_tasks.py** (lines 59-62, 167-170) — claim happens before `get_job_by_id`; since `claim_job()` returns False on missing job, the explicit not-found branches are dead code. Either drop them, or — if kept as defensive guards — match the `ingestion_tasks.py` pattern with a comment explaining why the branch is unreachable.
- [ ] **backend/tests/unit/tasks/test_emission_recalculation_tasks.py** (lines 222-223, 482-483) and **backend/tests/unit/services/data_ingestion/test_background_tasks.py** (lines 90-91) — tests mock `claim_job=True` while `get_job_by_id=None`, a state the real repo cannot produce. Either flip these to test the realistic `claim_job=False` early-return, or drop them when the dead branches above are removed.

### Deferred (tracked, no action this PR)

- [ ] **backend/app/tasks/\_poller.py** — `dispatch_job` reads `meta.provider_name`/`meta.filters`/`job_type` that current creation paths don't persist, so most orphan jobs are picked up and silently skipped. Plan A's docstring (lines 37-39) and Plan C explicitly defer this to the unified `run_job(job_id)` runner. Confirm Plan C tracks it; nothing to fix in this PR.
