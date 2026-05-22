# Bot Review TODOs: PR #1267

## Source Branch: `fix/1266-provider-scope-unit-sync-and-year-config`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR makes **unit sync** and **year configuration** provider-scoped end-to-end so multiple providers (e.g., TEST and ACCRED) can independently provision and open the same year within a shared database, preventing cross-provider interference.

**Changes:**

- Scope `YearConfiguration` by `(year, provider)` (composite PK) and update reads/writes across API/task/provider code paths to filter by provider.
- Plumb `current_user.provider` into newly created `DataIngestionJob` rows and update `unit_sync_handler` to use `job.provider` (rejecting `DEFAULT`).
- Add/update unit + integration tests to validate provider isolation and ensure the TEST provider can run unit sync using fixtures.

### Reviewed changes

Copilot reviewed 16 out of 16 changed files in this pull request and generated 4 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                            | Description                                                                                                    |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| docs/src/database/erd.md                                                                        | Updates ERD to reflect provider being part of `year_configuration`’s primary key.                              |
| backend/app/models/year_configuration.py                                                        | Adds `provider` to `YearConfiguration` and makes PK composite `(year, provider)`.                              |
| backend/app/api/v1/year_configuration.py                                                        | Scopes year-configuration CRUD/listing and audit chain behavior by provider.                                   |
| backend/app/api/v1/data_sync.py                                                                 | Scopes year-provisioning checks and unit-sync job creation by provider.                                        |
| backend/app/tasks/unit_sync_tasks.py                                                            | Uses `job.provider` to resolve providers; stamps `configuration_completed` per provider.                       |
| backend/app/providers/unit_provider.py                                                          | Implements TEST provider `fetch_all_units`/`map_api_unit` for unit_sync compatibility.                         |
| backend/app/services/data_ingestion/base_reduction_objective_csv_provider.py                    | Stores reduction objectives into provider-scoped `year_configuration`.                                         |
| backend/tests/unit/tasks/test_handler_registrations.py                                          | Adds unit tests ensuring provider is used and DEFAULT is rejected in unit_sync.                                |
| backend/tests/unit/providers/test_unit_provider.py                                              | Adds unit test validating TEST fixtures round-trip through `fetch_all_units`/`map_api_unit`.                   |
| backend/tests/integration/v1/test_year_configuration_list.py                                    | Adds integration tests validating per-provider isolation for same year + provider-scoped POST existence check. |
| backend/tests/integration/services/data_ingestion/test_travel_pg.py                             | Updates YearConfiguration lookups to use composite PK in PG integration tests.                                 |
| backend/tests/integration/services/data_ingestion/conftest.py                                   | Updates seeding helper to use composite PK and set provider when creating YearConfiguration.                   |
| backend/tests/integration/services/data_ingestion/test_sync_units_endpoint_pg.py                | Ensures mocked current_user includes `.provider` for provider-scoped queries/job creation.                     |
| backend/tests/integration/services/data_ingestion/test_plan_310b_factor_reupload_endpoint_pg.py | Ensures mocked current_user includes `.provider` for provider-scoped queries/job creation.                     |
| backend/tests/integration/services/data_ingestion/test_dispatch_copy_from_previous_year_pg.py   | Ensures mocked current_user includes `.provider` for provider-scoped queries/job creation.                     |

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 19 out of 19 changed files in this pull request and generated 3 comments.

---

### File: `backend/app/api/v1/year_configuration.py` (Line 343) — Copilot

The create_audit_entry docstring says the data_snapshot “always includes provider”, but the snapshots passed from create_year_configuration/update_year_configuration don’t include provider. Either include provider in the snapshot/diff payload or update the docstring to avoid misleading future readers about recoverability.

---

### File: `backend/app/api/v1/year_configuration.py` (Line 417) — Copilot

## list_year_configurations() now filters by current_user.provider. The docstring above still says backoffice data managers “see every row”, which is no longer true across providers; update it to clarify results are provider-scoped (admins still bypass only the is_started filter).

### File: `backend/app/tasks/unit_sync_tasks.py` (Line 175) — Copilot

## unit_sync is now provider-scoped (job.provider drives provider selection), but the phase status_message still says “Fetching units from Accred…”. This will be misleading for TEST runs and any future providers; make status/progress messages (and ideally the handler docstring) provider-neutral or include the provider name dynamically.

### File: `backend/app/api/v1/data_sync.py` (Line 2078) — Copilot

## Since this endpoint now sets job.provider from current_user.provider (provider-scoped unit sync), the surrounding naming/text still hardcodes “Accred API” (function name/docstring and the SyncStatusResponse message below). That becomes misleading for TEST and any future providers; adjust the wording to be provider-agnostic or include the provider name dynamically.

### File: `backend/alembic/versions/2026_05_22_1142-6293d5b22dc5_year_configuration_provider_scope_1266.py` (Line 56) — Copilot

The new `provider` column is created with `server_default="DEFAULT"`, which will also apply to _future_ inserts if a code path forgets to set `provider` (silently writing rows into the DEFAULT scope and breaking per-provider isolation). Consider a 2-step migration: add column nullable + server_default to backfill existing rows, then `ALTER COLUMN` to drop the server default (and keep it NOT NULL) once existing rows are stamped.

---

### File: `backend/alembic/versions/2026_05_22_1142-6293d5b22dc5_year_configuration_provider_scope_1266.py` (Line 66) — Copilot

`downgrade()` recreates a primary key on `year` only. After this migration, the table can legitimately contain multiple rows with the same `year` (one per provider), so the downgrade will fail with duplicate key errors. If downgrade support is required, add an explicit cleanup step (e.g., delete non-DEFAULT rows or error with a clear message) before recreating the single-column PK.

---

### File: `backend/app/api/v1/year_configuration.py` (Line 344) — Copilot

## `create_audit_entry`’s docstring no longer follows the Args/Returns structure used throughout this module (e.g., `save_uploaded_file`). Since this helper has a non-trivial signature, consider restoring the parameter docs and adding the new provider-scoping explanation as an extra paragraph to keep documentation consistent and easier to maintain.

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/alembic/versions/2026_05_22_1142-6293d5b22dc5_year_configuration_provider_scope_1266.py`** — `downgrade()` recreates a single-column PK on `year`, which fails with duplicate-key errors as soon as the DB carries rows for two providers at the same year (which is the entire reason this migration exists). Fix: in `downgrade()`, delete every row whose `provider != 'DEFAULT'` before `create_primary_key`, so the remaining set is unique on `year`. v0.x drops the DB between deploys so the data loss is acceptable; the alternative — raising a `RuntimeError` with a clear "manual cleanup required" message — is also acceptable. Either way, don't leave it silently broken.

### Maintainability / refactoring

- [ ] **`backend/app/tasks/unit_sync_tasks.py`** (line 169) and **`backend/app/api/v1/data_sync.py`** (lines 2044, 2054, 2099) — ACCRED-specific wording leaked into now-provider-agnostic code: `status_message="Fetching units from Accred…"`, function `sync_units_from_accred`, docstring `"Sync units from Accred API"`, response `message="Unit sync from Accred API scheduled"`. TEST runs surface misleading copy. Fix: parameterize each user-visible string with `job.provider.name` / `current_user.provider.name`. **Skip the function rename** — it's just a Python identifier (route is `POST /sync/units`), and renaming churns no contract but does churn imports.
- [ ] **`backend/app/api/v1/year_configuration.py`** (line 343 docstring) — Claims `data_snapshot` "always includes provider" but the three call sites (lines 552-555, 724-727, 904-907) build snapshots with only `is_started` + `config`. Fix: add `"provider": current_user.provider.name` to all three snapshot dicts — makes the audit log self-describing and matches the docstring. (Alternative: correct the docstring. Adding the field is the more useful direction since the encoded `entity_id` alone is opaque to a human reader.)
- [ ] **`backend/app/api/v1/year_configuration.py`** (line 402 docstring on `list_year_configurations`) — Says backoffice data managers "see every row"; post-change they only see every row _within their own provider scope_ (the `is_started` filter is what `is_admin` actually bypasses now). Fix: one-line docstring update — "Admins bypass the `is_started` filter; both views are scoped to `current_user.provider`."

_Dropped as non-actionable: line 56 (`server_default="DEFAULT"`) — the bot's diagnosis is real (DB doesn't block forgotten `provider=`) but the suggested 2-step migration is overkill for v0.x (DB is dropped between deploys, no rows to backfill) and would diverge from the existing `units` / `users` / `data_ingestion_jobs` convention which uses the same pattern. Line 344 (docstring Args/Returns format) — pure style nitpick._
