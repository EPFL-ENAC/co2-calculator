# Plan: Manual emission recalculation endpoint with "needs recalculation" status

**TL;DR**: Three additions. (1) Expose `GET /sync/recalculation-status?year=YYYY` returning per-module status (with per-data-entry-type detail nested inside), derived from existing `DataIngestionJob` rows. (2) Expose `POST /sync/recalculate-emissions/{module_type_id}/{data_entry_type_id}?year=YYYY` for single-type recalculation. (3) Expose `POST /sync/recalculate-emissions/{module_type_id}?year=YYYY` for module-level bulk recalculation with an `only_stale` flag (selectable via a frontend dialog). No auto-trigger on factor ingestion. No new DB table — status is derived from `DataIngestionJob.id` ordering.

---

### Phase 1 — Repository: cross-module DataEntry query

_add 1 method_

1. Add `list_by_data_entry_type_and_year(data_entry_type_id, year) -> list[DataEntry]` to `backend/app/repositories/data_entry_repo.py`
   - JOIN: `DataEntry ⋈ CarbonReportModule ⋈ CarbonReport WHERE data_entry_type_id=X AND CarbonReport.year=Y`
   - Models already imported in the repo file

---

### Phase 1.5 — Schema + Repository: recalculation status derivation

_no new DB table — derived from existing `DataIngestionJob` rows_

2. Add two Pydantic models to `backend/app/api/v1/data_sync.py` (alongside existing response models):

   ```python
   class RecalculationStatus(BaseModel):
       """Per-(module_type_id, data_entry_type_id) recalculation status."""
       module_type_id: int
       data_entry_type_id: int
       year: int
       needs_recalculation: bool
       last_factor_job_id: Optional[int]
       last_factor_job_result: Optional[IngestionResult]
       last_recalculation_job_id: Optional[int]
       last_recalculation_job_result: Optional[IngestionResult]

   class ModuleRecalculationStatus(BaseModel):
       """Per-module rollup status — true if any data_entry_type needs recalculation."""
       module_type_id: int
       year: int
       needs_recalculation: bool  # any(det.needs_recalculation for det in data_entry_types)
       data_entry_types: list[RecalculationStatus]
   ```

   The `ModuleRecalculationStatus` aggregation is computed in the API layer (no extra query): group the flat `RecalculationStatus` rows returned by the repo method by `module_type_id`, then set `needs_recalculation = any(row.needs_recalculation for row in group)`.

3. Add `get_recalculation_status_by_year(year: int) -> list[RecalculationStatusRow]` to `backend/app/repositories/data_ingestion.py`:

   **Derivation logic** — for each `(module_type_id, data_entry_type_id, year)`:
   - **Factor jobs** in scope: `is_current=True, year=Y, state=FINISHED, target_type=FACTORS, result != ERROR` — grouped by `(module_type_id, data_entry_type_id)`, keeping the row with `MAX(id)` (latest factor sync across all ingestion methods)
   - **Recalculation jobs** in scope: `is_current=True, year=Y, target_type=DATA_ENTRIES, ingestion_method=computed` — one per `(module_type_id, data_entry_type_id)` (unique because of the `is_current` partial-unique index)
   - LEFT JOIN factor groups with recalculation jobs on `(module_type_id, data_entry_type_id)`
   - `needs_recalculation = recalc_job IS NULL OR latest_factor_job.id > recalc_job.id`

   _Rationale_: `DataIngestionJob.id` is a serial primary key — a higher `id` means a later job. This comparison reliably detects whether factor data is newer than the last emission recalculation without any additional timestamp column.

   The method returns a lightweight dataclass/TypedDict (not the full ORM model) to avoid loading the `meta` JSON for every job.

---

### Phase 2 — Workflow: `EmissionRecalculationWorkflow`

_new file + implement existing stub_

2. Create `backend/app/workflows/emission_recalculation.py` with method `recalculate_for_data_entry_type(data_entry_type_id, year) -> dict`:
   - Fetch entries via Phase 1 repo method
   - For each: `DataEntryEmissionService.upsert_by_data_entry(DataEntryResponse.model_validate(entry))` — `DataEntryResponse` maps 1:1 to `DataEntry` fields, direct `model_validate` works
   - Per-entry errors: `except Exception` → log + accumulate in `error_details`, never abort
   - Collect affected `carbon_report_module_ids`; after the loop call `CarbonReportModuleService.recompute_stats()` once per distinct module
   - Return `{recalculated: N, modules_refreshed: M, errors: K, error_details: [...]}`

3. Implement `FactorService.find_modules_for_recalculation()` stub at `backend/app/services/factor_service.py` (L252) using the same repo method (_parallel with step 2_)

---

### Phase 3 — Task: background recalculation runner

_new file — mirrors `run_sync_task` session pattern_

4. Create `backend/app/tasks/emission_recalculation_tasks.py` with:

   **Single-type variant** (used by the per-data-entry-type endpoint):

   ```python
   async def run_recalculation_task(
       module_type_id: int,
       data_entry_type_id: int,
       year: int,
       job_id: int,
   ) -> None
   ```

   - Opens **two** `SessionLocal()` contexts following the same pattern as `run_sync_task`: `job_session` for status updates (commits immediately, visible to SSE), `data_session` for emission writes (single atomic commit at the end)
   - Phase sequence via `job_session` updates:
     1. `RUNNING` / `"Starting emission recalculation..."`
     2. After repo query: `"Found {N} data entries to recalculate"`
     3. `"Recalculating emissions..."`
   - Calls `EmissionRecalculationWorkflow(data_session).recalculate_for_data_entry_type(data_entry_type_id, year)`
   - On success: `await data_session.commit()`, then updates job → `FINISHED / SUCCESS` with `meta.recalculation` stats
   - On error: `await data_session.rollback()`, updates job → `FINISHED / ERROR` with `status_message`

   ```python
   def run_recalculation(module_type_id: int, data_entry_type_id: int, year: int, job_id: int) -> None
   ```

   - Sync wrapper (mirrors `run_ingestion`): calls `asyncio.run(run_recalculation_task(...))`

   **Module-level (multi-type) variant** (used by the per-module endpoint):

   ```python
   async def run_module_recalculation_task(
       module_type_id: int,
       data_entry_type_ids: list[int],
       year: int,
       job_id: int,
   ) -> None
   ```

   - Same dual-session pattern (`job_session` / `data_session`)
   - Iterates over `data_entry_type_ids` in sequence:
     - Per type: updates job `status_message = "Recalculating {data_entry_type} ({i}/{N})..."` via `job_session`
     - Calls `EmissionRecalculationWorkflow(data_session).recalculate_for_data_entry_type(type_id, year)`
     - Accumulates stats per type into `meta.recalculation = {type_id: stats, ...}`
   - A per-type error does **not** abort remaining types — accumulated in stats
   - `data_session.commit()` is called **once after all types are done** (all-or-nothing for the whole module)
   - Final job result: `SUCCESS` if no errors across all types; `WARNING` if any type had partial errors; `ERROR` only if all types failed

   ```python
   def run_module_recalculation(module_type_id: int, data_entry_type_ids: list[int], year: int, job_id: int) -> None
   ```

   - Sync wrapper: calls `asyncio.run(run_module_recalculation_task(...))`

---

### Phase 4 — Endpoint: `POST /sync/recalculate-emissions/{module_type_id}/{data_entry_type_id}`

_add to `backend/app/api/v1/data_sync.py`_

5. New endpoint with path params `module_type_id: ModuleTypeEnum`, `data_entry_type_id: DataEntryTypeEnum`, and **required** query param `year: int`:

   ```
   POST /sync/recalculate-emissions/{module_type_id}/{data_entry_type_id}?year=2025
   ```

   - **Permission**: `require_permission("backoffice.data_management", "sync")`
   - Validates `year` is provided (400 if missing)
   - Creates a `DataIngestionJob` **directly** via `DataIngestionRepository(db).create_ingestion_job()` — no provider needed:
     - `module_type_id`: from path
     - `data_entry_type_id`: from path
     - `year`: from query
     - `ingestion_method = IngestionMethod.computed`
     - `target_type = TargetType.DATA_ENTRIES`
     - `entity_type = EntityType.MODULE_PER_YEAR`
     - `state = IngestionState.NOT_STARTED`
     - `meta = {"config": {"year": year, "data_entry_type_id": data_entry_type_id.value}}`
   - Commits job creation, then schedules `run_recalculation` via `background_tasks.add_task`
   - Returns `SyncStatusResponse(job_id=job_id, state=NOT_STARTED, message="Emission recalculation scheduled")`
   - Client streams progress via existing **`GET /sync/jobs/{job_id}/stream`** — no new SSE endpoint needed

---

### Phase 4.5 — Endpoint: `POST /sync/recalculate-emissions/{module_type_id}` (module-level bulk trigger)

_add to `backend/app/api/v1/data_sync.py`_

6. New module-level endpoint:

   ```
   POST /sync/recalculate-emissions/{module_type_id}?year=2025&only_stale=true
   ```

   - **Permission**: `require_permission("backoffice.data_management", "sync")`
   - Path param `module_type_id: ModuleTypeEnum`; required query param `year: int`; optional `only_stale: bool = True`
   - Resolves candidate `data_entry_type_ids` from `MODULE_TYPE_TO_DATA_ENTRY_TYPES[module_type_id]`
   - If `only_stale=True`: calls `DataIngestionRepository(db).get_recalculation_status_by_year(year)`, filters to types where `needs_recalculation=True` that also belong to this module; returns 400 with `"No data entry types require recalculation for this module"` if none qualify
   - If `only_stale=False`: uses all data_entry_types for the module
   - Creates **one** `DataIngestionJob` directly via `DataIngestionRepository`:
     - `module_type_id`: from path
     - `data_entry_type_id = None` (multi-type job — not scoped to a single type)
     - `year`: from query
     - `ingestion_method = IngestionMethod.computed`
     - `target_type = TargetType.DATA_ENTRIES`
     - `entity_type = EntityType.MODULE_PER_YEAR`
     - `state = IngestionState.NOT_STARTED`
     - `meta = {"config": {"year": year, "data_entry_type_ids": [...], "only_stale": only_stale}}`
   - Commits job creation, schedules `run_module_recalculation` via `background_tasks.add_task`
   - Returns `SyncStatusResponse(job_id=job_id, state=NOT_STARTED, message="Module emission recalculation scheduled for {N} data entry types")`
   - Client streams progress via existing `GET /sync/jobs/{job_id}/stream`

---

### Phase 4.6 — Endpoint: `GET /sync/recalculation-status`

_add to `backend/app/api/v1/data_sync.py`_

7. New read endpoint:

   ```
   GET /sync/recalculation-status?year=2025
   ```

   - **Permission**: `require_permission("backoffice.data_management", "view")`
   - Required query param `year: int` (400 if missing)
   - Calls `DataIngestionRepository(db).get_recalculation_status_by_year(year)` → flat `list[RecalculationStatus]`
   - Groups by `module_type_id` in the API layer → `list[ModuleRecalculationStatus]`
   - Returns `[]` if no completed FACTORS jobs exist for the year

---

### Phase 5 — Frontend: status display + recalculation actions

_`frontend/src/pages/back-office/DataManagementPage.vue`_

8. On page load (and after any factor sync or recalculation job completes), call `GET /sync/recalculation-status?year=YYYY`:
   - Store results as `list[ModuleRecalculationStatus]` in reactive state, keyed by `module_type_id`
   - **Module-level row/card**: show **"Recalculation needed"** warning badge when `module.needs_recalculation=true`; show success/warning chip when `false` (using `last_recalculation_job_result` of the most recently recalculated data_entry_type)
   - **Per-data-entry-type sub-row**: show individual `needs_recalculation` badge + `last_recalculation_job_result` chip using `module.data_entry_types`

9. **Module-level "Recalculate Emissions" button** (shown on each module card regardless of `needs_recalculation`; disabled while a module-level recalculation is in progress):
   - On click: opens a **Quasar `q-dialog`** with the choice:
     - `"Recalculate only data entry types that need it"` (default, maps to `only_stale=true`)
     - `"Recalculate all data entry types"` (maps to `only_stale=false`)
   - The dialog shows which data_entry_types are stale (from reactive status) to help the operator decide
   - On confirm: `POST /sync/recalculate-emissions/{module_type_id}?year=YYYY&only_stale={bool}` → receive `job_id`
   - Subscribe to SSE on `GET /sync/jobs/{job_id}/stream`; show inline module-level progress spinner + `status_message`
   - On `stream_closed`: refresh recalculation-status → all badges update reactively
   - On `FINISHED`: show module-level result badge and per-type stats from `meta.recalculation`

10. **Per-data-entry-type "Recalculate Emissions" button** (existing, unchanged from previous design):
    - On click: `POST /sync/recalculate-emissions/{module_type_id}/{data_entry_type_id}?year=YYYY` → receive `job_id`
    - Subscribe to SSE; show inline progress; on `stream_closed` refresh status

---

### Phase 6 — Tests

_parallel with implementation phases_

11. `backend/tests/unit/repositories/test_data_entry_repo.py` — test `list_by_data_entry_type_and_year()`: matching year, non-matching year, empty result
12. `backend/tests/unit/repositories/test_data_ingestion_repo.py` (extend) — test `get_recalculation_status_by_year()`:
    - FACTORS job only (no recalculation job) → `needs_recalculation=True`
    - FACTORS job + recalculation job where `recalc.id > factor.id` → `needs_recalculation=False`
    - FACTORS job + recalculation job where `factor.id > recalc.id` → `needs_recalculation=True`
    - FACTORS job with `result=ERROR` → excluded → no status row returned
    - No FACTORS jobs at all → empty list
13. `backend/tests/unit/workflows/test_emission_recalculation.py` (NEW) — all-success, partial error (one entry fails), empty set
14. `backend/tests/unit/tasks/test_emission_recalculation_tasks.py` (NEW):
    - `run_recalculation_task` — updates job RUNNING → FINISHED/SUCCESS; error path → FINISHED/ERROR
    - `run_module_recalculation_task` — iterates all given types; one type error → WARNING result; all types error → ERROR result; verifies `data_session.commit()` called once; verifies per-type progress `status_message` updates

---

### Relevant files

- `backend/app/repositories/data_entry_repo.py` — Phase 1 addition
- `backend/app/repositories/data_ingestion.py` — Phase 1.5 addition (`get_recalculation_status_by_year`)
- `backend/app/api/v1/data_sync.py` — Phase 1.5 (`RecalculationStatus` + `ModuleRecalculationStatus` models), Phase 4 (per-type POST), Phase 4.5 (module-level POST), Phase 4.6 (GET status)
- `backend/app/workflows/emission_recalculation.py` — Phase 2 (new)
- `backend/app/services/factor_service.py` L252 — Phase 2 stub implementation
- `backend/app/tasks/emission_recalculation_tasks.py` — Phase 3 (new, both single-type and module-level tasks)
- `frontend/src/pages/back-office/DataManagementPage.vue` — Phase 5
- `backend/app/tasks/ingestion_tasks.py` — **no changes**

---

### Verification

1. After a successful FACTORS job for `(module X, data_entry_type Y, year 2025)`, call `GET /sync/recalculation-status?year=2025` → module X appears with `needs_recalculation=true`; its `data_entry_types` array contains Y with `needs_recalculation=true`
2. Module-level dialog opens; select "only stale" → `POST /recalculate-emissions/{module_type_id}?year=2025&only_stale=true` → single `job_id` returned
3. SSE on `GET /sync/jobs/{job_id}/stream` shows `"Recalculating {data_entry_type} (1/N)..."` per type, then final stats in `meta.recalculation`
4. After completion, `GET /sync/recalculation-status?year=2025` → module X `needs_recalculation=false`, all data_entry_types `needs_recalculation=false`
5. Run a new FACTORS job → status flips back to `needs_recalculation=true` for that type/module automatically
6. Select "all data entry types" in dialog with `only_stale=false` → all types recalculated even if not stale
7. `only_stale=true` when no types are stale → 400 with clear error message
8. Break one DataEntry → module job finishes `WARNING`; per-type stats in `meta.recalculation` show `errors=1` for that type, others unaffected
9. `pytest backend/tests/unit/repositories/test_data_ingestion_repo.py -v`
10. `pytest backend/tests/unit/workflows/test_emission_recalculation.py -v`
11. `pytest backend/tests/unit/tasks/test_emission_recalculation_tasks.py -v`

---

### Further Considerations

1. **Scale / batching**: if a unit has thousands of DataEntries, the recalculation loop may be slow. A `BATCH_SIZE`-limited iterator with intermediate `flush()` + progress updates (reusing the pattern from `process_csv_in_batches`) would prevent memory spikes. This can be deferred if current data volumes are small.
2. **Idempotency**: the endpoint can be called multiple times safely — `upsert_by_data_entry()` already deletes existing emissions before re-inserting. The `is_current` flag on `DataIngestionJob` will naturally track the latest recalculation job for a given `(module_type_id, data_entry_type_id, year)` combination.
3. **Multi-method factor jobs**: a `(module_type_id, data_entry_type_id, year)` may have both a CSV and a computed FACTORS `is_current` job. The status derivation takes `MAX(id)` across all ingestion methods for that combination, so the most recent factor sync (regardless of method) is what matters.
4. **No migration needed**: `needs_recalculation` is fully derived from existing `DataIngestionJob` rows. The `is_current` partial-unique index already ensures at most one current job per `(module_type_id, data_entry_type_id, target_type, ingestion_method, year)` combination.
5. **Module-level job `data_entry_type_id=None`**: the `is_current` unique partial index on `DataIngestionJob` covers `(module_type_id, data_entry_type_id, target_type, ingestion_method, year)`. With `data_entry_type_id=NULL`, PostgreSQL's NULL ≠ NULL semantics mean the uniqueness constraint won't prevent multiple concurrent module-level jobs. The `mark_job_as_current` method will need to handle this (`WHERE data_entry_type_id IS NULL`) explicitly to unset previous module-level jobs.
