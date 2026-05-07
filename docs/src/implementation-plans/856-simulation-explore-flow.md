---
status: delivered
last_updated: 2026-05-06
branch: feat/856-simulation-explore-flow
base_commit: 7e6de8a427a205fab81092485104be7edf6a9a44
commits:
  - 253943adb refactor: replace simulator detection with carbon report type mapping
  - 7b3d90224 feat: enhance carbon report schema and background processing
  - 285c6db41 refactor: replace custom unit access check with centralized policy enforcement
  - 368f4a471 refactor: simplify project retrieval logic in CarbonReportService
---

# Issue 856 — Simulation Explore Flow

Summary of all backend changes made after commit `7e6de8a` (which introduced the `?carbon_project_type` query-param migration).

---

## 1. API contract: remove `X-Co2-Simulation`, use `?carbon_project_type`

### Why

Using a client-sent header (`X-Co2-Simulation: 1`) to decide whether a request should resolve against Simulator vs Calculator reports was brittle and easy to spoof. The Simulator/Calculator distinction is now derived from the explicit query parameter `carbon_project_type`, which is validated server-side and maps deterministically to `CarbonReportType`.

### Backend changes

**File:** `backend/app/api/v1/carbon_report_module.py`

- The request header resolver `_resolve_is_simulator(request)` was removed.
- A new query param was added to all module endpoints:
  - `carbon_project_type: int = Query(default=0, ge=0, le=2)`
- The param is mapped via `_resolve_carbon_report_type(carbon_project_type)`:
  - `0 → CALCULATOR`
  - `1 → SIMULATOR_EXPLORE`
  - `2 → SIMULATOR_PLAN`

**File:** `backend/app/api/v1/carbon_report_module_stats.py`

- The `Request` dependency was removed from `GET /{carbon_report_id}/validated-totals`.
- `validated_only` is now derived from the DB report type (join `CarbonReport → CarbonProject`) instead of any client signal:
  - `validated_only = report_type != SIMULATOR_EXPLORE`
  - Unknown `carbon_report_id` defaults to `validated_only=True` (safe default).

### Frontend changes

**File:** `frontend/src/api/http.ts`

The ky client no longer sets `X-Co2-Simulation`. For simulation routes, it now appends `?carbon_project_type=1` to the request URL in `beforeRequest`, so all simulator requests are explicit and consistent with backend resolution.

---

## 2. Schema: `last_updated` exposed on `CarbonReportRead`

**File:** `backend/app/schemas/carbon_report.py`

`last_updated: Optional[int]` was added to `CarbonReportRead`. The field was already persisted in the DB but not returned by the API, which meant the GET explore endpoint could not compute the TTL age on the client (or in the background-task logic).

---

## 3. Unique constraints added (model + migration)

### Why

`bulk_upsert` in `CarbonReportRepository` previously used `ON CONFLICT (unit_id, year)`. That index was dropped when `carbon_project_id` replaced the old uniqueness model, causing a runtime crash. Two named unique constraints were added to fix the conflict target and to enforce data integrity at the DB level.

### Model changes

**`backend/app/models/carbon_project.py`**

```python
__table_args__ = (
    UniqueConstraint("unit_id", "carbon_report_type", name="uq_carbon_projects_unit_type"),
)
```

Guarantees at most one `CarbonProject` per `(unit_id, carbon_report_type)` combination (e.g., one Calculator project and one Simulator-Explore project per unit).

**`backend/app/models/carbon_report.py`**

```python
__table_args__ = (
    UniqueConstraint("carbon_project_id", "year", name="uq_carbon_reports_project_year"),
)
```

Guarantees at most one `CarbonReport` per `(carbon_project_id, year)`.

### Migration

**`backend/alembic/versions/2026_05_04_0945-05d68c9a6054_add_simulation_carbon_reports.py`**

Two `op.create_unique_constraint` calls added to `upgrade()` and two `op.drop_constraint` calls added to `downgrade()`. Consolidated into the existing migration rather than creating a separate file.

### Repository fix

**`backend/app/repositories/carbon_report_repo.py`**

```python
# Before
.on_conflict_do_nothing(index_elements=["unit_id", "year"])

# After
.on_conflict_do_nothing(constraint="uq_carbon_reports_project_year")
```

---

## 4. Simulator Explore endpoints: GET/POST split + TTL background task

**File:** `backend/app/api/v1/carbon_report.py`

### Before

A single `GET` endpoint (`get_or_create_simulator_explore_carbon_report`) combined retrieval and creation, and managed the 24 h TTL inline by deleting the old report and creating a new one before returning — which blocked the response.

### After

**`GET /simulator/explore/unit/{unit_id}/reference-year/{reference_year}/`**

- Returns the existing explore report or 404 (never creates).
- Computes `age = now - last_updated`.
- If `last_updated` is `None` or `age > 24 h`, schedules `_refresh_explore_background` as a FastAPI `BackgroundTasks` task and still returns the stale report immediately so the user is not blocked.

**`POST /simulator/explore/unit/{unit_id}/reference-year/{reference_year}/`** (status 201)

- Calls `service.create_explore(...)` and commits.
- Pure creation; callers are responsible for not calling this if a report already exists.

**`_refresh_explore_background(unit_id, old_report_id, reference_year)`**

Background coroutine that opens its own `SessionLocal` session (same pattern as audit sync tasks), deletes the stale report, and creates a fresh one. Runs after the response is sent.

```python
_EXPLORE_TTL_SECONDS = 24 * 60 * 60
```

All four call sites to the old `_require_unit_access` local function were updated to the imported `require_unit_access` (see §4).

---

## 5. `require_unit_access` centralised in `policy.py`

**File:** `backend/app/core/policy.py`

The ad-hoc `_require_unit_access` function that lived in `carbon_report.py` duplicated role-walking logic and used a hand-rolled institutional_id check that diverged from the rest of the codebase. It was replaced by a shared helper added to `policy.py`:

```python
def require_unit_access(current_user: User, unit: Unit | None) -> None:
```

Key differences vs. the old implementation:

| Old `_require_unit_access`                                              | New `require_unit_access`                                                             |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Walked `role.on` dict/attr manually                                     | Uses `pick_role_for_institutional_id` (same function used by all other access checks) |
| Checked `role.on.get("institutional_id")` or `role.on.institutional_id` | Delegates to `role_priority` module                                                   |
| Defined locally in `carbon_report.py`                                   | In `app.core.policy`; importable everywhere                                           |

All four call sites in `carbon_report.py` updated from `_require_unit_access(...)` to `require_unit_access(...)`.

---

## 6. `CarbonReportService`: get/create separation

**File:** `backend/app/services/carbon_report_service.py`

### `_get_or_create_project` → `_get_project` + `_create_project`

The single method was split into two pure methods:

- `_get_project(unit_id, report_type) -> Optional[CarbonProject]` — read-only, never mutates.
- `_create_project(unit_id, report_type) -> CarbonProject` — write-only, always creates.

Call sites use the `or` short-circuit idiom:

```python
project = await self._get_project(unit_id, T) or await self._create_project(unit_id, T)
```

### `get_or_create_explore` → `get_explore` + `create_explore`

- `get_explore(unit_id, reference_year) -> Optional[CarbonReportRead]` — idempotent read; returns `None` if no report exists.
- `create_explore(unit_id, reference_year) -> CarbonReportRead` — creates the SIMULATOR_EXPLORE project (if absent), the report, and all module records. Sets `last_updated` to the current timestamp. Does **not** seed from the Calculator report (see §6).

TTL management moved entirely to the API layer (`_refresh_explore_background`).

### `_seed_research_facility_entries` removed

The method that copied research-facility `DataEntry` rows from the Calculator report into the new Explore report was removed. Simulator Explore is not supposed to contain Calculator data; the seeding was dead/incorrect behaviour.

Removed unused imports: `sa_select`, `sqm_col`, `DataEntry`, `ModuleTypeEnum`.

---

## 7. Tests

### `tests/unit/v1/test_carbon_report.py`

**Fixes:** Three existing tests were patching `module._require_unit_access`, which no longer exists in the module after the centralisation. Updated to `patch.object(module, "require_unit_access")`.

**New tests (5):**

| Test                                                              | What it asserts                                                                |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `test_get_simulator_explore_found_fresh_no_refresh`               | Fresh report returned; `background_tasks.add_task` not called                  |
| `test_get_simulator_explore_not_found_raises_404`                 | Missing report → HTTP 404                                                      |
| `test_get_simulator_explore_expired_schedules_background_refresh` | Stale report (>24 h) returned immediately; `add_task` called with correct args |
| `test_get_simulator_explore_null_last_updated_schedules_refresh`  | `last_updated=None` treated as expired                                         |
| `test_create_simulator_explore_commits_and_returns`               | POST calls `service.create_explore`, commits, returns report                   |

### `tests/unit/services/test_carbon_report_service.py`

**New tests (7):**

| Test                                                     | What it asserts                                                                                                                    |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `test_get_explore_returns_none_when_not_found`           | Returns `None` on empty DB                                                                                                         |
| `test_get_explore_is_idempotent_on_empty_db`             | Two consecutive calls both return `None`                                                                                           |
| `test_create_explore_creates_report_and_modules`         | Report created with correct `year`/`unit_id`; all modules auto-created as `NOT_STARTED`                                            |
| `test_get_explore_returns_existing_report`               | Round-trip: `create_explore` then `get_explore` returns same ID                                                                    |
| `test_get_explore_does_not_cross_units`                  | Different `unit_id` returns `None`                                                                                                 |
| `test_get_explore_does_not_cross_years`                  | Different `reference_year` returns `None`                                                                                          |
| `test_bulk_upsert_resolves_project_ids_before_repo_call` | Service enriches all items with non-null `carbon_project_id`; both unit_id=1 rows share one project; unit_id=2 gets a distinct one |

### `tests/unit/v1/test_carbon_report_module_stats.py` (new file)

Tests the security fix in `get_validated_totals`: `validated_only` is derived from `CarbonProject.carbon_report_type` (DB join), not from any client-supplied signal.

| Test                                                                    | `report_type`       | Expected `validated_only` |
| ----------------------------------------------------------------------- | ------------------- | ------------------------- |
| `test_get_validated_totals_calculator_uses_validated_only_true`         | `CALCULATOR`        | `True`                    |
| `test_get_validated_totals_simulator_explore_uses_validated_only_false` | `SIMULATOR_EXPLORE` | `False`                   |
| `test_get_validated_totals_simulator_plan_uses_validated_only_true`     | `SIMULATOR_PLAN`    | `True`                    |
| `test_get_validated_totals_unknown_report_id_uses_validated_only_true`  | `None` (unknown ID) | `True` (safe default)     |

Each test asserts both the `DataEntryEmissionService` and `DataEntryService` calls receive the correct `validated_only` kwarg.
