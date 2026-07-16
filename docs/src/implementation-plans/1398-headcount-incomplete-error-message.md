---
status: proposed
issue: 1398
last_updated: 2026-07-07
title: "Clarify re-upload vs recalculate messaging on partial CSV ingestion"
summary: "Partial/failed CSV ingestion jobs must tell the user to re-upload the file, not just recalculate, when rows were skipped or never reached."
---

# Clarify re-upload vs recalculate messaging on partial CSV ingestion

## Problem

Headcount (and any module) CSV upload that stops partway through (issue: processed only 3000 rows) leaves the job in a state whose message tells the user to "recalculate" without saying the file needs to be re-uploaded. Recalculating only recomputes emissions for rows already committed to the DB — it cannot add the rows that were never ingested. Users read "recalculate" as the fix, click it, and the missing rows stay missing.

Root cause is shared, not headcount-specific: `BaseCSVProvider` (`backend/app/services/data_ingestion/base_csv_provider.py`), used by every module CSV importer including headcount, computes `SUCCESS` / `WARNING` / `ERROR` from `rows_processed` / `rows_skipped` in `_compute_ingestion_result` and writes a generic summary in `_finalize_and_commit`:

```python
status_message = (
    f"Processed {stats['rows_processed']} rows: "
    f"{stats['rows_with_factors']} with factors, "
    f"{stats['rows_without_factors']} without factors, "
    f"{stats['rows_skipped']} skipped"
)
```

This message never mentions re-uploading. Separately, the frontend (`UploadCard.vue` + `useUploadCard.ts`) surfaces the job's `status_message` verbatim in the error/warning banner (`getErrorDetails`), and independently shows a "Recalculation Needed" badge with a "Retry recalculation" button (`data_management_recalculation_needed`, `data_management_recalculate_retry` in `frontend/src/i18n/backoffice_data_management.ts`) whenever recalculation status is stale. Both can be visible at once, and neither tells the user which action actually restores the missing data.

If the job dies mid-stream (exception/timeout before `_finalize_and_commit` runs), the terminal message is whatever the failure handler wrote — also not reviewed for "you must re-upload" wording.

## Design

Two distinct situations, both currently collapse into the same vague UI:

1. **Partial ingestion (needs re-upload)**: `rows_skipped > 0` because the job stopped early (crash/timeout) or `rows_processed < total CSV rows`. Recalculating cannot fix this — the source rows were never written. The message must say so explicitly and point at re-upload, not recalculate.
2. **Recalculation genuinely sufficient**: all rows were ingested (`rows_skipped == 0` / job `SUCCESS`), but emissions are stale because factors or config changed. Here "Retry recalculation" is the correct and complete action — no re-upload needed.

Backend fix (single shared spot, covers headcount and every other CSV-backed module):

- In `_compute_ingestion_result` / `_finalize_and_commit`, when result is `WARNING` (partial) or an early-termination `ERROR`, append an explicit instruction to `status_message`, e.g.:
  `"... {rows_skipped} skipped. Re-upload the file to import the missing rows — recalculation alone will not add them."`
- Do the same in whatever failure/exception path sets the terminal job state before reaching `_finalize_and_commit` (mid-stream crash/timeout), so a hard stop at row 3000 also gets a "re-upload" message instead of a bare exception string.
- Only emit "recalculation is sufficient" phrasing (or say nothing extra) when the job actually completed with all rows processed.

Frontend fix:

- `UploadCard.vue` / `useUploadCard.ts` already renders `status_message` for WARNING/ERROR jobs — no new component needed, the backend message change flows through automatically.
- Where the "Recalculation Needed" badge/CTA can appear alongside a WARNING/ERROR data job (`hasErrorOrWarning(lastDataJob)`), suppress or relabel the recalc CTA so it doesn't read as the sole fix — e.g. keep both visible but make the upload card's own re-upload button (`data_management_reupload_data`, already shown when `lastDataJob` exists) the primary call-to-action, and gate "Retry recalculation" copy to not imply it replaces re-upload.

No backend API/schema change; `status_message` is a free-text field already piped to the frontend.

## Steps

- [ ] In `base_csv_provider.py::_finalize_and_commit`, extend the WARNING-path `status_message` to explicitly instruct re-upload when `rows_skipped > 0`.
- [ ] Locate the mid-stream failure handler that sets job state before `_finalize_and_commit` runs (job crash/timeout path) and apply the same re-upload wording there.
- [ ] Confirm `_compute_ingestion_result` classification is untouched (SUCCESS stays silent — no re-upload prompt when all rows landed).
- [ ] Frontend: verify `UploadCard.vue`'s error/warning banner renders the updated `status_message` without truncation.
- [ ] Frontend: where `hasErrorOrWarning(lastDataJob)` is true, ensure the "Recalculation Needed" / "Retry recalculation" CTA doesn't read as a standalone fix (copy tweak in `backoffice_data_management.ts`, or conditional ordering so re-upload is primary).
- [ ] Add/update i18n strings (en/fr) for the new backend-driven wording if any static frontend copy changes.
- [ ] Regression test: CSV ingestion that stops partway (simulate `rows_skipped > 0` / mid-stream failure) asserts `status_message` contains re-upload instruction, distinct from the all-rows-succeeded case.
