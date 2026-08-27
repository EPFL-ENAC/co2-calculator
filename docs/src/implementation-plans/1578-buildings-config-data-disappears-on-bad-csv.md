---
status: delivered
issue: 1578
last_updated: 2026-07-07
title: "Fix: failed CSV re-upload blanks previous upload summary in backoffice config"
summary: "A failing re-upload is marked as the module's current job, so the shared UploadCard hides the prior successful job's filename/rows/download info even though the underlying data is untouched — UNLESS the failed re-upload's CSV passes header validation but has every row invalid, in which case the prior data is actually deleted (see 'Caveat found during implementation' below)."
---

# Fix: failed CSV re-upload blanks previous upload summary in backoffice config

## Problem

Uploading an invalid CSV to a module in backoffice config (reported for
Buildings) makes the previously-uploaded data appear to vanish from the
config page. The uploaded `DataEntry` rows are still present and still used
by the Calculator — this is a display bug, not data loss, **for CSVs that
fail structurally (bad/missing headers)**. See the caveat below: a CSV that
passes header validation but has every row fail per-row validation causes
real data loss, not just a display bug.

## Caveat found during implementation (step 1 verification)

Step 1's data-integrity check (below) was run against two classes of "bad
CSV" and got two different answers:

1. **Header-invalid CSV** (missing/wrong columns) — `_validate_csv_headers`
   raises before the pre-import delete ever runs. Confirmed via integration
   test: prior `DataEntry` rows are untouched (2 rows before, 2 rows after).
   This is the scenario the rest of this plan's root-cause analysis and fix
   address, and it is purely a display bug.
2. **Content-invalid CSV** (valid headers, every row fails per-row
   validation, e.g. an out-of-range `sius_code`) — `process_csv_in_batches`
   already ran `_delete_existing_entries_for_module_per_year` before the row
   loop. Since every row fails via `handler.validate_create` (caught,
   recorded as a soft row error, no exception raised), `rows_processed == 0`
   and `_compute_ingestion_result` returns `ERROR`, but the handler _returns
   normally_ — it never raises. `app/tasks/runner.py`'s `run_job` treats a
   non-raising handler as `handler_succeeded = True` regardless of the
   embedded `result`, and unconditionally calls `data_session.commit()`.
   That commits the DELETE with nothing inserted to replace it. Confirmed
   via integration test: 2 rows before, **0 rows after** — the prior
   successful upload's data is permanently gone.

   `csv_ingest_handler`'s own comment ("No data*entries committed (or
   partial state we don't trust)") is incorrect for this path — data \_can*
   be committed even when `result == ERROR`.

This is a distinct, more severe bug than the one this plan fixes, and it is
plausibly the actual mechanism behind the original Buildings report (a
content-invalid CSV is a more common real-world mistake than a
structurally-invalid one). **The `mark_job_as_current` fix below does not
address it** — with the fix, an operator will see the config UI look
correct (still pointing at the last "current" job) but if that CSV was the
content-invalid kind, the underlying data is gone and the UI is now
_wrong_, not just uninformative. This needs its own fix (e.g. don't delete
before rows are known to insert successfully, or roll back when
`rows_processed == 0`) and is out of scope for this PR — flagged for
owner triage before closing #1578.

## Design

Confirmed: display bug, and confirmed shared across all modules, not
Buildings-specific.

Root cause is in `DataIngestionRepository.mark_job_as_current`
(`backend/app/repositories/data_ingestion.py:1306`). It flips `is_current`
onto any job whose `state` is `RUNNING` or `FINISHED` — it does not check
`result`. A CSV validation failure still reaches `state=FINISHED,
result=ERROR` (`base_csv_provider.py:709-717`), so `mark_job_as_current`
demotes the previous successful job and promotes the new failed one as the
module's current job, unconditionally.

`get_latest_jobs_by_year` (`data_ingestion.py:1282`) filters on
`is_current`, so `latest_data_job` / `latest_common_data_job` in the year
config API response now points at the failed job. That job's `meta` only
contains `{"config": ..., "error": str(e)}` (`base_provider.py:230-232`) —
`processed_file_path` and `rows_processed` are only written on the success
path (`base_csv_provider.py:1389`, `:1429`), so the failed job's meta never
carries them.

On the frontend, `useModuleConfig.getImportRow` (`frontend/src/composables/useModuleConfig.ts:82-88`) passes this job straight through as `lastJob`.
`UploadCard.vue` gates the entire filename/rows-imported/download block on
`v-if="lastJob?.meta"` (line 266) — meta exists (it's not undefined) but
lacks the fields `getJobInfo` reads (`useUploadCard.ts:100-119`), so
`fileName`/`rowsProcessed`/`timestamp` all resolve to `undefined` and the
card renders as if nothing was ever uploaded, alongside the error banner
(`hasErrorOrWarning`, correctly shown). The prior successful job is still
in the DB and its `DataEntry` rows are untouched — nothing in the failure
path deletes or mutates them — but the UI has lost the pointer to summarize
them.

This logic lives entirely in module-agnostic code: `mark_job_as_current`
is keyed by `(module_type_id, target_type, year, ingestion_method,
data_entry_type_id)` with no module-specific branching, and `UploadCard.vue`
/ `useUploadCard.ts` is the single shared component every module's
data/factor/reference card renders through (per
`780-bug-backoffice-configuration-page.md`). Any module where a user
re-uploads a failing CSV after a prior success hits the same blanking.
Buildings is just the module the reporter happened to test.

Fix belongs in `mark_job_as_current`: only promote a `FINISHED` job to
`is_current` when `result != ERROR`. A failed re-upload should surface its
error (still queryable/visible via job history) without evicting the last
good job from the "current" slot the frontend renders from. `RUNNING` jobs
keep being marked current (mid-flight visibility, unrelated to this bug).

## Steps

- [x] Confirm server-side data integrity: for a module/year with a
      successful ingestion job followed by a failed re-upload, verify via
      DB query (or an integration test) that `DataEntry` rows from the
      successful job are unchanged in count and content, and that the
      Calculator's emission computation for that module is unaffected —
      establishes this is purely a display regression before touching UI.
      **Result: true only for header/structurally-invalid CSVs — see
      "Caveat found during implementation" above for the content-invalid
      case, which does lose data.**
- [x] Fix `mark_job_as_current` (`backend/app/repositories/data_ingestion.py`)
      to skip promoting `is_current` when `job.state == FINISHED and
job.result == IngestionResult.ERROR` (keep `WARNING`/`SUCCESS`
      promoting, since those still carry usable meta and are the closest
      "latest attempt" the user should see).
- [x] Verify `hasErrorOrWarning` / error banner still surfaces the failed
      attempt somewhere the user can see it happened (e.g. job list/toast)
      even though it no longer becomes `latest_data_job` — confirm no
      regression where upload failures become silently invisible.
      **Confirmed: `useDataEntryDialog.ts`'s `subscribeToJobUpdates`
      callback fires a `$q.notify` toast keyed off the job-update SSE
      payload's own `result`, independent of `is_current` — so the failure
      is still surfaced at upload time. The in-card persistent error banner
      (`UploadCard.vue`'s `hasErrorOrWarn`, driven by `lastJob`) does stop
      showing once the card reverts to the last successful job — expected,
      since `lastJob` is no longer the failed one. No frontend change made;
      flagging here since the plan asked to verify, not silently accept.**
- [x] Add a regression test at the repository level asserting a FINISHED+
      ERROR job does not demote a FINISHED+SUCCESS job's `is_current` flag,
      and that `get_latest_jobs_by_year` keeps returning the successful job.
- [~] Manually verify in backoffice config: upload a good CSV, then an
  invalid one, for a non-Buildings module (e.g. Travel) to confirm the
  fix isn't module-scoped and the shared component now behaves
  correctly everywhere. **Not done as a manual UI walkthrough; instead
  added a second repository-level regression test using
  `module_type_id=2` (professional_travel) proving the same contract
  holds for a non-Buildings module — consistent with
  `mark_job_as_current` having no module-specific branching.**
