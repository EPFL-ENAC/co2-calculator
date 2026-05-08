# Bot Review TODOs: PR #1026

## Source Branch: `feat/310c-observability-columns`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds observability plumbing for ingestion jobs by introducing persistent `started_at` / `finished_at` timestamps alongside repository helpers and tests, so later pipeline-runner work can measure total job wall-clock duration separately from per-attempt locking.

**Changes:**

- Add nullable `started_at` / `finished_at` columns to `data_ingestion_jobs` via Alembic and SQLModel.
- Add repository support for idempotent `started_at` stamping and optional `finished_at` stamping.
- Add unit and Postgres integration coverage for the new observability fields.

### Reviewed changes

Copilot reviewed 5 out of 5 changed files in this pull request and generated 3 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                 | Description                                                                         |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `backend/tests/unit/repositories/test_data_ingestion_repo.py`                        | Adds unit tests for `set_started_at` idempotency and `finished_at` updates.         |
| `backend/tests/integration/services/data_ingestion/test_observability_columns_pg.py` | Adds Postgres round-trip coverage for the new timestamp columns.                    |
| `backend/app/repositories/data_ingestion.py`                                         | Extends repository APIs with `finished_at` support and new `set_started_at` helper. |
| `backend/app/models/data_ingestion.py`                                               | Adds `started_at` and `finished_at` fields to `DataIngestionJob`.                   |
| `backend/alembic/versions/2026_05_05_1000-d3e5f7a9b1c4_add_started_finished_at.py`   | Adds the schema migration and merges the current Alembic heads.                     |

</details>

---

### File: `backend/app/repositories/data_ingestion.py` (Line 131) — Copilot

## `claim_job()` commits the RUNNING transition before this helper is called, so a pod crash in between leaves `started_at` NULL. When the sweep later retries the job, the retry becomes the recorded start time, and `finished_at - started_at` underreports the total wall-clock duration instead of surviving retries as described.

### File: `backend/app/repositories/data_ingestion.py` (Line 87) — Copilot

## This API lets callers set `finished_at=True` independently of the lifecycle state. A RUNNING/QUEUED update can therefore persist a terminal timestamp on a non-terminal job, which breaks the column contract and any duration calculations built on it. The timestamp should be derived from, or validated against, a `FINISHED` transition.

### File: `backend/app/repositories/data_ingestion.py` (Line 87) — Copilot

## Because `finished_at` is opt-in here, repository-owned terminal paths that do not go through this flag still leave the new column NULL (for example `cancel_job()` and the auto-abandon branch in `sweep_stuck_running_jobs`). Any observability query that relies on `finished_at` will silently miss cancelled or exhausted jobs.

## Action Items

### Critical: logic, security, correctness

- [ ] **backend/app/repositories/data_ingestion.py** (line 131): `claim_job()` commits the RUNNING transition before `set_started_at` is invoked, so a crash in that gap leaves `started_at` NULL and the sweep retry later overwrites the true start. Stamp `started_at` inside the same transaction as the RUNNING transition (or unconditionally backfill on retry-claim) so total wall-clock survives retries.
- [ ] **backend/app/repositories/data_ingestion.py** (line 87): The `finished_at=True` flag lets callers persist a terminal timestamp on a RUNNING/QUEUED job, breaking the column contract. Derive `finished_at` from a FINISHED state transition (or validate the target lifecycle state inside the helper) instead of accepting it as an independent boolean.
- [ ] **backend/app/repositories/data_ingestion.py** (line 87): Terminal paths that do not pass `finished_at=True` (notably `cancel_job()` and the auto-abandon branch of `sweep_stuck_running_jobs`) leave `finished_at` NULL, so observability queries miss cancelled/exhausted jobs. Stamp `finished_at` from every terminal transition, not just the success path.
