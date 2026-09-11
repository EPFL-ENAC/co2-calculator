---
status: delivered
issue: 2442
last_updated: 2026-09-11
title: "Backoffice CSV download served the wrong file"
summary: "Root cause: archive paths keyed by a recyclable job_id collided across DB resets on shared envs; the file endpoint also cached indefinitely. Fixed both, plus made the collision structurally impossible going forward."
---

# Backoffice CSV download served the wrong file

## Problem

Reported (Martina, #2442): clicking "download last CSV" on a backoffice
data-management card returned content that didn't match the card (e.g. the
headcount student-factors card downloaded member-factors content). Not
reproducible locally.

## Investigation

Traced the full click path first (`SubmoduleItem.vue` → `UploadCard.vue` →
`useSubmoduleConfig.downloadLastCsv` → `GET /api/v1/files/{path}?d=true`) —
every hop is keyed explicitly by `data_entry_type_id`/the job's own
`processed_file_path`, never by array index. No frontend bug found; ruled
out via two independent traces plus reading the actual deployed JS bundle
(matched current source, so it wasn't stale-deploy either).

Decisive evidence came from direct, authenticated requests against the live
file endpoint, bypassing the frontend entirely:

- `GET .../files/processed/5/headcount_students_factors.csv` (no query) and
  the same path with `?d=true` returned **different content** at first —
  pointing at an intermediary cache. That was real (fixed below) but turned
  out to be a second, independent bug, not the reported one.
- Listing the S3 folder `processed/5/` directly showed **8 unrelated
  files** — buildings, reduction-objectives, headcount data, headcount
  member _and_ student factors, plus two garbage-named test uploads —
  spanning **March through June 2026**, all sharing the same `job_id=5`
  folder.
- `headcount_students_factors.csv` in that folder is dated **18.05.2026** —
  over three months before the job the app calls "job 5" today
  (`completed_at: 2026-09-03T14:19:10`). That job could not have written a
  file dated May.

## Root cause

`processed/{job_id}/` and `processing/{job_id}/` name their folder with
nothing but the bare auto-increment integer `DataIngestionJob.id`. On a
shared environment whose DB gets manually reset/reseeded without file
storage being cleared alongside it, that id gets recycled across
completely unrelated jobs, weeks or months apart — proven by the 8 files
above.

`_move_to_processed`'s idempotency guard (added for #1559's stuck-job
retry: "a file already exists here → this must be my own prior attempt →
skip the move") trusted bare path existence as proof of identity. When a
fresh, correctly-parsed job's `job_id` happened to recycle onto a path some
unrelated older job had already claimed, the guard silently kept that
unrelated leftover instead of archiving what the current job had just
parsed. Zero errors anywhere: the DB-side factor values are computed and
stored independently at ingest time and were always correct — only the
archived file served back by the download button was wrong.

Separately, `GET /api/v1/files/{path}` sent no `Cache-Control` at all,
which independently let some layer between the browser and the backend
cache a response indefinitely and replay it after the underlying file was
already correct.

## Fix

Three changes, `backend/`:

1. **`app/api/v1/files.py`** — `Cache-Control: no-store` on every file
   response. It's also permission-gated (`backoffice.configuration.view`)
   with no per-user cache key, so an intermediary cache was a potential
   cross-user leak vector too, not just a staleness bug.
2. **`app/services/data_ingestion/base_provider.py`** — `_move_to_processed`
   now always (re-)writes the destination instead of skipping when
   something's already there. For a genuine same-job retry the content is
   identical anyway (harmless no-op); for the collision case it's the
   actual fix. `_move_to_processing`'s own skip-if-exists is left alone —
   it's load-bearing for #1559 (failure there is fatal by design) and its
   exposure window is much smaller since `processing/` empties out on
   completion rather than accumulating for months like `processed/` did.
3. **Belt-and-suspenders**: new `_archive_folder()` helper names the
   folder `{job_id}-{created_at:%Y%m%dT%H%M%S%f}` instead of the bare id —
   uses the job's existing `created_at` (no migration), sourced from
   `self.job` when set or `self.config["created_at"]` (already spread from
   `job.__dict__` on the background-worker reconstruction path), falling
   back to the bare id if neither is available. `job_id` alone still tells
   apart anything created in the same instant; `created_at` tells apart
   anything sharing the same id across a DB reset. Applied in both
   `base_provider.py` and `base_reduction_objective_csv_provider.py` (which
   had its own independent copy of the old `processed/{job_id}/...` format
   string — now calls the same helper instead of duplicating it).

Regression tests added/updated: `test_files_download_disposition.py`
(Cache-Control), `test_base_provider.py` (`_move_to_processed` overwrite
behavior + `_archive_folder` naming/fallback/collision cases).

## Follow-up (not code, tracked separately)

The shared dev/stage environments already have months of orphaned files
sitting in `processed/`/`processing/` from past id collisions (each
environment is its own S3 bucket). Whoever resets one of those DBs going
forward should also clear its `processed/`/`processing/` prefixes — the
naming fix stops _new_ collisions but doesn't retroactively clean up what's
already there.
