# Implementation Plan: Unify CSV Upload Ingestion

## Goal

Unify CSV upload + API sync under one job-creation pipeline that stores file paths in job `meta`, dispatches providers via the factory, and exposes job status via SSE.

## Non-Goals

- Redesigning the ingestion model schema.
- Implementing new providers beyond the equipment CSV provider.

## Current State (Summary)

- Uploads go through `POST /files/tmp` and return `FileNode.path`.
- Job creation happens in `POST /sync/data-entries/{module_type_id}` with `ingestion_method`.
- SSE streams only status fields, not identifiers.

## Target Flow

1. Client uploads CSV to `files/tmp` → gets `file_path`.
2. Client calls `POST /sync/data-entries/{module_type_id}` with:
   - `ingestion_method=csv`
   - `target_type`
   - `year`
   - `config.file_path=<uploaded path>`
3. Backend creates `DataIngestionJob`, enqueues ingestion.
4. Provider reads `file_path` from `config`/`meta`.
5. Client subscribes to SSE to map updates to module/target rows.

## Required Changes

### Backend

1. Extend `SyncRequest` to accept `file_path` (or ensure `config.file_path` is passed through).
2. Store `file_path` in job `meta` at creation.
3. Ensure CSV providers read `file_path` from `config` or `meta`.
4. SSE payload must include identifiers:
   - `job_id`, `module_type_id`, `target_type`, `year`, `status`, `status_message`, `updated_at`.

### Frontend

1. Upload via `files/tmp`, store returned `file_path`.
2. Call `initiateSync()` with `ingestion_method=csv` and `config.file_path`.
3. Add SSE listener in Pinia to update per module/target status.

## example of /files response

```json
[
  {
    "name": "seed_equipment_data.csv",
    "path": "tmp/1770110939379406/seed_equipment_data.csv",
    "size": 6683,
    "mime_type": "text/csv",
    "is_file": true,
    "children": []
  }
]
```

## Where to find upload interface?

- modal and store for upload frontend
  : frontend/src/components/organisms/data-management/FilesUploadDialog.vue
  : frontend/src/stores/files.ts
