---
status: delivered
issue: 1559
last_updated: 2026-08-21
title: "Idempotent tmp->processing (and processing->processed) file moves on job retry"
summary: "Skip the move if the destination already exists so a retried ingestion job doesn't fail on a file a prior attempt already consumed."
---

**Delivered.** `DataIngestionProvider._move_to_processing` /
`_move_to_processed` (`backend/app/services/data_ingestion/base_provider.py:64-108`)
implement the idempotency check exactly as designed below, with regression
coverage in `backend/tests/unit/services/data_ingestion/test_base_provider.py`.
Found still-current while investigating
[#2220](https://github.com/EPFL-ENAC/co2-calculator/issues/2220) — this
plan's own frontmatter was stale (said "proposed"), which is corrected here
per the guardrails' "keep plans aligned with shipped code."

# Idempotent tmp->processing (and processing->processed) file moves on job retry

## Problem

**Symptom.** After a backend restart, CSV ingestion intermittently fails with:
`Processing failed: Failed to move file from tmp/<ts>/headcount_data.csv to processing/<job_id>/headcount_data.csv`

**Root cause: the `tmp -> processing` move is not idempotent on retry.**

1. The move consumes the source. `BaseCSVProvider._setup_and_validate` (`backend/app/services/data_ingestion/base_csv_provider.py:1113-1116`, confirmed still current) calls `files_store.move_file(tmp_path, processing_path)` (a `shutil.move`) and raises if it returns falsy.
2. `move_file` returns `False` only when the source is missing. In `enacit4r_files/services/local.py:308`, a missing source raises `FileNotFoundError` internally, caught and converted to `return False`. So the error means _the tmp source is already gone_, not a permissions/disk problem.
3. A retry finds the source already consumed — the first attempt already `shutil.move`d it into `processing/<job_id>/`. The move is a one-shot consume with no "already done" branch.
4. A restart triggers the retry. `sweep_stuck_running_jobs` (`backend/app/repositories/data_ingestion.py:1135`) resets stale `RUNNING` jobs to `NOT_STARTED` so `claim_job` re-dispatches them. Its own docstring flags a no-heartbeat duplicate-run hazard (a long job past `STALE_JOB_TIMEOUT_MINUTES`, or a crash after the move). So: restart after the move → job re-queued → `_setup_and_validate` runs again → move fails on the already-moved file.

This explains "sometimes": it only fails when the crash/restart lands _after_ the move but before the job is marked FINISHED. Data is never lost — it sits safely in `processing/<job_id>/`; the retry just refuses to recognize it.

**Affected code (same pattern duplicated across all four `DataIngestionProvider` subclasses):**

| Move            | File                                       | Line (verified 2026-07-07) |
| --------------- | ------------------------------------------ | -------------------------- |
| tmp->processing | `base_csv_provider.py`                     | 1113-1116                  |
| tmp->processing | `base_factor_csv_provider.py`              | 260-265                    |
| tmp->processing | `base_reduction_objective_csv_provider.py` | 261-270                    |
| tmp->processing | `csv_providers/reference_data.py`          | 228-230                    |

The later `processing -> processed` moves share the same retry hazard:

- `base_csv_provider.py:1378` (issue cited 1452; drifted, still present)
- `base_factor_csv_provider.py:552`
- `base_reduction_objective_csv_provider.py:448`
- `csv_providers/reference_data.py:247`

`DataIngestionProvider` (shared ABC, `backend/app/services/data_ingestion/base_provider.py:24`) is the natural home for a centralized helper. `files_store.file_exists` exists on the same service as `move_file` (`enacit4r_files/services/local.py:253`), so the idempotency check needs no new dependency.

## Design

Make each move idempotent: if the destination already exists, a prior attempt already did the move — skip it instead of failing.

```python
filename = tmp_path.split("/")[-1]
processing_path = f"processing/{self.job_id}/{filename}"
if await self.files_store.file_exists(processing_path):
    logger.info(f"File already at {processing_path} (prior attempt); skipping move")
else:
    if not await self.files_store.move_file(tmp_path, processing_path):
        raise Exception(f"Failed to move file from {tmp_path} to {processing_path}")
```

Centralize as two helpers on `DataIngestionProvider` (`base_provider.py`) rather than patching four call sites independently (DRY, and it forecloses a fifth copy of the bug landing in a future provider):

- `_move_to_processing(tmp_path: str) -> str` — tmp->processing, returns `processing_path`.
- `_move_to_processed(processing_path: str) -> str` — processing->processed, returns `processed_path`.

Both check destination existence before calling `move_file`, log-and-skip when already present, and raise only when the move is actually attempted and fails. Call sites (all four providers, both move points each) replace their inline `move_file` + raise blocks with a call to the shared helper.

## Steps

- [ ] Add `_move_to_processing(tmp_path) -> str` and `_move_to_processed(processing_path) -> str` to `DataIngestionProvider` in `backend/app/services/data_ingestion/base_provider.py`, each guarded by a `file_exists` check on the destination before calling `move_file`.
- [ ] Replace the inline tmp->processing move in `base_csv_provider.py:1113-1116` with `self._move_to_processing(tmp_path)`.
- [ ] Replace the inline tmp->processing move in `base_factor_csv_provider.py:260-265` with the same helper call.
- [ ] Replace the inline tmp->processing move in `base_reduction_objective_csv_provider.py:261-270` with the same helper call.
- [ ] Replace the inline tmp->processing move in `csv_providers/reference_data.py:228-230` with the same helper call.
- [ ] Replace the four processing->processed moves (`base_csv_provider.py:1378`, `base_factor_csv_provider.py:552`, `base_reduction_objective_csv_provider.py:448`, `csv_providers/reference_data.py:247`) with `self._move_to_processed(processing_path)`.
- [ ] Add a regression test: place the file in `processing/<job_id>/` (simulating a prior attempt) with no source in `tmp/`, run the provider's setup, and assert it succeeds (reads from `processing/`) instead of raising "Failed to move file". Cover at least one provider directly and rely on the shared helper for the rest.
- [ ] Out of scope: the deeper `STALE_JOB_TIMEOUT_MINUTES` / no-heartbeat duplicate-run issue (Plan 310C per the `sweep_stuck_running_jobs` docstring) is the underlying trigger for duplicate runs. The idempotent move fixes this symptom directly without touching the job runner; leave 310C as a separate, later plan.
