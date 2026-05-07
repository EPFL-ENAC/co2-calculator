# Bot Review TODOs: PR #962

## Source Branch: `feat/856-simulation-explore-flow`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Introduces an end-to-end **Simulator Explore** flow spanning DB schema, backend report/project services, simulation-mode request handling, and a new frontend Explore UI that reuses existing module/submodule components and emissions breakdown charts.

**Changes:**

- Adds **carbon projects** + simulator report get-or-create logic (with TTL) and seeds Explore from a reference Calculator report.
- Adds **simulation-mode** plumbing (context var + header-driven middleware) and updates backend queries/policy checks accordingly.
- Implements the **SimulationExplorePage** UI and refactors frontend emissions breakdown refresh flow away from pub/sub.

### Reviewed changes

Copilot reviewed 38 out of 38 changed files in this pull request and generated 13 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                           | Description                                                                                       |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| frontend/src/stores/workspace.ts                                                               | Extends `CarbonReport` typing and adds selection helper for simulator explore report.             |
| frontend/src/stores/modules.ts                                                                 | Replaces breakdown pub/sub with a conditional refresh helper after mutations.                     |
| frontend/src/router/routes.ts                                                                  | Hides breadcrumbs on simulation routes.                                                           |
| frontend/src/pages/app/SimulationsPage.vue                                                     | Links “Explore” CTA to the explore route.                                                         |
| frontend/src/pages/app/SimulationExplorePage.vue                                               | Builds the Explore page UI, prefetches submodule data/counts, fetches breakdown.                  |
| frontend/src/i18n/simulation.ts                                                                | Adds i18n strings for the Explore page.                                                           |
| frontend/src/components/organisms/module/SubModuleSection.vue                                  | Adds `collapsible` prop and improves submodule item count fallback sources.                       |
| frontend/src/components/organisms/module/ModuleForm.vue                                        | Forces `HeadcountMemberSelect` to remount when member count changes.                              |
| frontend/src/components/organisms/module/ModuleCharts.vue                                      | Removes emission breakdown refresh-sequence watcher; now relies on store fetch/invalidation flow. |
| frontend/src/components/organisms/module/HeadcountMemberSelect.vue                             | Extracts member fetch to a dedicated function.                                                    |
| frontend/src/components/layout/Co2Header.vue                                                   | Adjusts workspace display + logo routing behavior for simulation pages.                           |
| frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue                          | Refactors props to runtime-typed `defineProps` and tweaks header layout classes.                  |
| frontend/src/api/http.ts                                                                       | Adds `X-Co2-Simulation` header injection for simulation routes.                                   |
| docs/src/database/erd.md                                                                       | Updates ERD to include `carbon_projects` and new `carbon_reports` relationships/fields.           |
| backend/tests/unit/services/test_data_entry_emission_service.py                                | Updates unit tests for new report lookup behavior in emission service.                            |
| backend/tests/unit/repositories/test_data_entry_repo.py                                        | Updates tests to create `CarbonProject` and link reports via `carbon_project_id`.                 |
| backend/tests/unit/repositories/test_data_entry_emission_repo.py                               | Updates tests to create `CarbonProject` and link reports via `carbon_project_id`.                 |
| backend/tests/unit/repositories/test_carbon_report_repo.py                                     | Updates repo tests to include `carbon_project_id` in creates.                                     |
| backend/tests/conftest.py                                                                      | Ensures `make_carbon_report` factory auto-creates a Calculator `CarbonProject` when needed.       |
| backend/app/services/unit_totals_service.py                                                    | Guards previous-year lookup against missing `year`.                                               |
| backend/app/services/data_entry_emission_service.py                                            | Adds report lookup + “percentage_of_last_year” override logic for emissions.                      |
| backend/app/services/carbon_report_service.py                                                  | Adds project resolution + get-or-create Explore report + seeding logic.                           |
| backend/app/services/carbon_report_module_service.py                                           | Routes module lookup to Explore report modules when in simulation mode.                           |
| backend/app/schemas/carbon_report.py                                                           | Extends schemas with `reference_year` and `carbon_project_id`.                                    |
| backend/app/repositories/data_entry_repo.py                                                    | Bypasses validated-only filters when in simulation mode.                                          |
| backend/app/repositories/data_entry_emission_repo.py                                           | Bypasses validated-only filters when in simulation mode.                                          |
| backend/app/repositories/carbon_report_repo.py                                                 | Updates listing/getting logic to join through `CarbonProject` and adds Explore lookup.            |
| backend/app/repositories/carbon_report_module_repo.py                                          | Adds Explore-module lookup and improves report-module deletion behavior.                          |
| backend/app/models/carbon_report.py                                                            | Introduces `CarbonReportType` enum and adds `carbon_project_id` + `reference_year` fields.        |
| backend/app/models/carbon_project.py                                                           | Adds new `CarbonProject` model (project grouping by type/unit).                                   |
| backend/app/models/**init**.py                                                                 | Registers `CarbonProject` in model rebuild/export.                                                |
| backend/app/main.py                                                                            | Adds middleware to set `SIMULATION_MODE` from request header.                                     |
| backend/app/core/simulation_mode.py                                                            | Introduces request-scoped `SIMULATION_MODE` context var.                                          |
| backend/app/core/policy.py                                                                     | Bypasses module permission checks when in simulation mode.                                        |
| backend/app/api/v1/carbon_report_module_stats.py                                               | Treats all modules as validated when in simulation mode for breakdown logic.                      |
| backend/app/api/v1/carbon_report.py                                                            | Adds GET endpoint to get-or-create Simulator Explore report.                                      |
| backend/alembic/versions/2026_04_28_1440-451937f20b2d_add_last_roles_sync_at_to_users_table.py | Removes prior migration (replaced by the new migration chain).                                    |
| backend/alembic/versions/2026_04_27_1612-092cf12fa429_add_simulation_carbon_report_support.py  | Adds migration for simulation support / carbon projects & new report fields.                      |

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 41 out of 41 changed files in this pull request and generated 11 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 46 out of 46 changed files in this pull request and generated 3 comments.

<details>
<summary>Comments suppressed due to low confidence (1)</summary>

**backend/app/repositories/carbon_report_repo.py:42**

- `bulk_upsert()` uses `ON CONFLICT (unit_id, year) DO NOTHING`, but this PR removes the `(unit_id, year)` uniqueness constraint/index on `carbon_reports` (and moves report type to `carbon_projects`). In Postgres, this will fail at runtime with “no unique or exclusion constraint matching the ON CONFLICT specification”, and even if it didn’t, duplicates for Calculator reports would make `get_by_unit_and_year()` ambiguous.

Suggestion: reintroduce a uniqueness guarantee and align the conflict target (e.g. unique on `(carbon_project_id, year)` and use that in `ON CONFLICT`, or keep a Calculator-only unique index and use `on_conflict_do_nothing(constraint=...)`).

```
    async def bulk_upsert(self, data: list[CarbonReportCreate]) -> list[CarbonReport]:
        """Bulk upsert carbon reports using INSERT ... ON CONFLICT DO NOTHING."""
        stmt = (
            insert(CarbonReport)
            .values([d.model_dump() for d in data])
            .on_conflict_do_nothing(index_elements=["unit_id", "year"])
            .returning(CarbonReport)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 46 out of 46 changed files in this pull request and generated 5 comments.

<details>
<summary>Comments suppressed due to low confidence (1)</summary>

**backend/app/api/v1/carbon_report.py:141**

- `GET /carbon-reports/{carbon_report_id}` does not apply `_require_unit_access()`, so any authenticated user who can guess/report IDs could retrieve reports outside their units. Since this file is introducing explicit unit-boundary enforcement, the ID-based endpoints should also validate access by looking up the report's unit (or joining through `carbon_project_id`) before returning it.

```
@router.get("/{carbon_report_id}", response_model=CarbonReportRead)
async def get_carbon_report(
    carbon_report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a carbon report by ID."""
    service = CarbonReportService(db)
    report = await service.get(carbon_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Carbon report not found")
    return report
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 45 out of 45 changed files in this pull request and generated 6 comments.

<details>
<summary>Comments suppressed due to low confidence (1)</summary>

**frontend/src/stores/modules.ts:832**

- `refreshEmissionBreakdownIfNeeded()` forces a refetch with `excludeModules=[]`, but `getEmissionBreakdown()` caches only by `carbonReportId` (it returns early when the id matches). After a mutation, this can prevent ResultsPage from ever refetching the breakdown with its own `exclude_modules` query params, leading to stale/incorrect breakdowns when some modules are intentionally excluded. Consider including `excludeModules` in the cache key (e.g., store a stable serialized exclude list alongside the report id) and/or have `refreshEmissionBreakdownIfNeeded` take the caller’s exclude list instead of hard-coding `[]`.
</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 42 out of 42 changed files in this pull request and generated 11 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 43 out of 43 changed files in this pull request and generated 6 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 44 out of 44 changed files in this pull request and generated 11 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 42 out of 42 changed files in this pull request and generated 12 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 42 out of 42 changed files in this pull request and generated 9 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 45 out of 45 changed files in this pull request and generated 11 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 46 out of 46 changed files in this pull request and generated 10 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 45 out of 45 changed files in this pull request and generated 7 comments.

<details>
<summary>Comments suppressed due to low confidence (1)</summary>

**backend/app/api/v1/carbon_report_module.py:916**

- The GET item endpoint fetches a DataEntry by `item_id` only, without verifying it belongs to the requested `unit_id/year/module_id/submodule_id` (or the resolved report type). This creates an IDOR risk: a user with access to one unit can potentially retrieve entries from another unit by guessing IDs. Please scope the lookup (resolve the expected CarbonReportModule via unit/year/carbon_project_type and ensure the DataEntry’s `carbon_report_module_id` and `data_entry_type_id` match) and return 404 on mismatch.

```
async def get(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_module_permission_for_unit(
        current_user=current_user,
        module_id=module_id,
        action="view",
        db=db,
        unit_id=unit_id,
    )

    logger.info(
        f"GET item: unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module_id={sanitize(module_id)}, item_id={sanitize(item_id)}"
    )
    item: Union[
        HeadcountItemResponse,
        DataEntryResponse,
    ]
    if ModuleTypeEnum[module_id.replace("-", "_")] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not supported for retrieval",
        )
    item = await DataEntryService(db).get(
        id=item_id,
    )
    logger.info(f"Retrieved item {sanitize(item_id)}")

    return item
```

</details>

---

### File: `backend/app/services/carbon_report_module_service.py` (Line null) — github-advanced-security[bot]

## CodeQL / Cyclic import

Import of module [app.services.carbon_report_service](1) begins an import cycle.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/621)

### File: `frontend/src/stores/modules.ts` (Line 847) — Copilot

## After post/patch/delete, you invalidate the cached emission breakdown but `refreshEmissionBreakdownIfNeeded()` returns early on non-simulation routes. This means Calculator module/results charts will keep showing stale breakdown data until the user changes report/year. Consider either (a) always refreshing after mutations, or (b) scoping the invalidation/refresh logic so non-simulation pages still trigger a refetch when needed.

### File: `frontend/src/pages/app/SimulationExplorePage.vue` (Line null) — Copilot

## `SubModuleSection` is passed `sub.type as any` for `submodule-type`, but the store APIs use the submodule _id_ (e.g. `getSubmoduleData({ submoduleType: sub.id })`). Passing `sub.type` here can route form submit/update/delete calls to the wrong API path and the `as any` hides the type error. Use the correct submodule identifier (likely `sub.id`) and drop the `any` cast.

### File: `backend/app/core/policy.py` (Line null) — Copilot

## The global `X-Co2-Simulation` header flips `SIMULATION_MODE` and completely bypasses module permission checks. Because clients can set this header on arbitrary requests, this becomes an authorization bypass for any endpoint guarded by `check_module_permission`. Simulation behavior should be enforced server-side (e.g., only for simulator endpoints / simulator reports, and still validating unit scope), not by trusting a client header.

### File: `backend/app/main.py` (Line null) — Copilot

## This middleware enables `SIMULATION_MODE` solely based on a client-controlled header and does so for _all_ routes. Combined with the permission bypass, this allows callers to opt into simulation mode on any API call. Restrict simulation mode activation to simulator-specific paths (or a server-side verified condition like a simulator report/project type) rather than trusting a header for global behavior changes.

### File: `backend/app/api/v1/carbon_report.py` (Line 152) — Copilot

## This endpoint is reachable with only `get_current_user` and does not perform any unit-scope/module permission check for the provided `unit_id`. With simulation mode bypassing `check_module_permission`, callers can potentially create/read simulator reports for units they should not access. Add an explicit authorization check tied to the unit scope (and keep it enforced even in simulation mode).

### File: `backend/app/repositories/carbon_report_repo.py` (Line null) — Copilot

`bulk_upsert()` uses `ON CONFLICT (carbon_project_id, year) DO NOTHING`, but the migration creates a (partial) unique index on `(unit_id, year)` (and does not create any unique constraint/index on `(carbon_project_id, year)`). Postgres requires the conflict target to match an existing unique constraint/index, otherwise this will raise at runtime. Align the conflict target with an actual unique index (or add the corresponding unique index in the migration).

```suggestion
            .on_conflict_do_nothing(index_elements=["unit_id", "year"])
```

---

### File: `frontend/src/pages/app/SimulationExplorePage.vue` (Line null) — Copilot

## `prefetchSubmoduleCounts()` fires one `getSubmoduleData` request per submodule (across all modules) on page mount. This can result in dozens of parallel API calls on every Explore page load and may noticeably slow the page / increase backend load. Consider adding a lightweight counts endpoint (or reusing module totals) so the page can render counts without fetching every submodule dataset up front.

### File: `backend/app/services/carbon_report_service.py` (Line null) — Copilot

## `_seed_research_facility_entries()` introduces inline imports. This makes dependencies harder to track and can hide circular-import issues; it also conflicts with the codebase guideline to keep imports at the top of the file. Move these imports to module scope (and keep them ordered stdlib → third-party → local).

### File: `backend/app/services/data_entry_emission_service.py` (Line 298) — Copilot

The `percentage_of_last_year` override path builds a `DataEntryEmission` without setting `scope`. For leaf emissions, `scope` is used elsewhere (and is set for CSV overrides / factor-based rows). Set `scope=emission_type.scope` here as well so overridden rows behave consistently in aggregations and breakdowns.

```suggestion
                                primary_factor_id=None,
                                scope=emission_type.scope,
```

---

### File: `backend/app/services/data_entry_emission_service.py` (Line 164) — Copilot

## This prior-year `CarbonReport` lookup is only filtered by `(unit_id, year)`. With Simulator reports, multiple reports can exist for the same unit/year, so `.one_or_none()` can raise `MultipleResultsFound` or select the wrong baseline. Constrain this lookup to the intended report type/project (e.g., join `CarbonProject` and require `CALCULATOR`).

### File: `backend/app/services/carbon_report_service.py` (Line null) — Copilot

## `get_or_create_explore()` introduces new TTL + delete/recreate behavior. Since `CarbonReportService` already has unit tests, adding coverage for the TTL reuse vs recreate cases would help prevent regressions.

### File: `backend/app/api/v1/carbon_report_module.py` (Line null) — Copilot

## `_resolve_is_simulator()` infers simulator context purely from whether a Simulator Explore report exists for `(unit_id, year)`. This can make non-simulation requests for that unit/year resolve against the Explore report and also bypass module permission checks (since `check_module_permission(..., is_simulator_report=True)` returns early). Simulator context should be derived from request context (e.g., `SIMULATION_MODE.get()` set by middleware) or an explicit report/project identifier, not DB existence alone.

### File: `backend/alembic/versions/2026_05_01_1147-ff9ea4a46fdf_add_simulation_carbon_reports.py` (Line null) — Copilot

This adds `carbon_projects.carbon_report_type` as `nullable=False` without a `server_default`/backfill. If `carbon_projects` already has rows, the migration will fail. Consider adding a default or a backfill step (nullable → populate → alter to non-null).

```suggestion
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE carbon_projects "
        "SET carbon_report_type = 'Calculator' "
        "WHERE carbon_report_type IS NULL"
    )
    op.alter_column(
        "carbon_projects",
        "carbon_report_type",
        existing_type=sa.Enum(
            "Calculator",
            "Simulator_Explore",
            "Simulator_Plan",
            name="carbon_report_type_enum",
        ),
        nullable=False,
    )
```

---

### File: `backend/alembic/versions/2026_05_01_1147-ff9ea4a46fdf_add_simulation_carbon_reports.py` (Line null) — Copilot

This adds `carbon_projects.is_viewable_by_unit_members` as `nullable=False` without a `server_default`/backfill. If `carbon_projects` already has rows, the migration will fail. Add a default/backfill step (or make it nullable, populate, then alter).

```suggestion
        sa.Column(
            "is_viewable_by_unit_members",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "carbon_projects",
        "is_viewable_by_unit_members",
        existing_type=sa.Boolean(),
        server_default=None,
    )
    op.alter_column(
```

---

### File: `frontend/src/pages/app/SimulationExplorePage.vue` (Line null) — Copilot

## `unitId` / `year` are computed as possibly `null`, but `SubModuleSection` requires `unitId: number` and `year: string | number`. As-is, this can cause type-check errors and runtime issues if the store isn't initialized (e.g., guard bypass / first load). Consider guarding/redirecting early and only rendering the module list once both values are available, or make the computed values non-nullable in this page.

### File: `frontend/src/pages/app/SimulationExplorePage.vue` (Line 197) — Copilot

## This page explicitly filters out `MODULES.ResearchFacilities` from the displayed modules, but the Explore flow description (and the intro text) states that users can explore research facilities impact and the backend seeds Explore reports with research facility entries. If Research Facilities should be part of the Explore UI, remove this filter (or adjust the seeding/UX copy to match).

### File: `backend/app/services/carbon_report_service.py` (Line null) — Copilot

## `_seed_research_facility_entries()` copies `DataEntry` rows into the Explore report but does not copy or recompute the corresponding `DataEntryEmission` rows. Since module stats/breakdowns read from `data_entry_emissions`, the seeded research facilities data will show zero emissions until emissions are recomputed elsewhere. Consider recomputing emissions for the new entries (or copying emissions when safe) during seeding.

### File: `backend/app/repositories/carbon_report_repo.py` (Line 65) — Copilot

## `list_by_unit()` now does an inner join to `carbon_projects`, which will exclude any existing `carbon_reports` rows where `carbon_project_id` is NULL. The migrations in this PR add `carbon_project_id` as nullable but do not backfill existing reports, so existing Calculator reports could disappear after upgrade. Backfill `carbon_project_id` in a migration, or handle NULLs (e.g., LEFT JOIN + fallback) during the migration window.

### File: `backend/app/api/v1/carbon_report.py` (Line 87) — Copilot

## `POST /carbon-reports/` creates a report without calling `_require_unit_access()`. This means an authenticated user could create Calculator reports for arbitrary `unit_id` values even if they don’t have access to that unit. Apply the same unit-boundary check here as in the list/get endpoints.

### File: `backend/alembic/versions/2026_05_01_1147-ff9ea4a46fdf_add_simulation_carbon_reports.py` (Line null) — Copilot

This migration drops the only uniqueness enforcement for Calculator reports (`uq_carbon_reports_unit_year_calculator`) and does not replace it with a new unique constraint/index (e.g. `(carbon_project_id, year)` or `(unit_id, year)` scoped via project type). That will (1) break `INSERT .. ON CONFLICT (unit_id, year)` statements (see `CarbonReportRepository.bulk_upsert`) and (2) allow duplicate Calculator reports, causing `scalar_one_or_none()` lookups to throw `MultipleResultsFound`.

Suggestion: add a new unique index/constraint that matches the post-migration data model and update repository upserts/lookups to use it.

```suggestion
    op.drop_column("carbon_reports", "carbon_report_type")
    op.create_index(
        "uq_carbon_reports_carbon_project_year",
        "carbon_reports",
        ["carbon_project_id", "year"],
        unique=True,
    )
```

---

### File: `backend/alembic/versions/2026_05_01_1147-ff9ea4a46fdf_add_simulation_carbon_reports.py` (Line null) — Copilot

## The migration drops the unique index `uq_carbon_reports_unit_year_calculator` and removes `carbon_reports.carbon_report_type`, but it doesn’t add any replacement uniqueness constraint under the new `carbon_projects` model. Without a new unique index (e.g., `(carbon_project_id, year)` and/or `(unit_id, carbon_report_type)` on projects), duplicate Calculator reports per unit/year become possible and `bulk_upsert()`/year-based selection logic can break.

### File: `backend/app/services/data_entry_emission_service.py` (Line 293) — Copilot

## `report` is only loaded when `year is None`, but `_get_year_from_data_entry()` always fetches the report internally and will normally return a non-null year. As a result, `report` stays `None` in production and the `percentage_of_last_year` override block never runs. Load the report explicitly when the override field is present (or have `_get_year_from_data_entry` return both year+report) so the override can actually be applied.

### File: `backend/alembic/versions/2026_05_01_1417-030717c03bd0_add_simulation_carbon_reports.py` (Line null) — Copilot

## The upgrade drops `uq_carbon_reports_unit_year_calculator` / `carbon_report_type` but does not create a replacement uniqueness constraint for Calculator reports under the new `carbon_projects` model. This allows duplicate Calculator reports per unit/year and also breaks `ON CONFLICT` logic in `CarbonReportRepository.bulk_upsert`. Add a new UNIQUE index/constraint (e.g., `(carbon_project_id, year)` for Calculator projects or enforce 1 Calculator project per unit + unique `(unit_id, year)` within that project) before dropping the old one.

### File: `backend/alembic/versions/2026_04_27_1612-092cf12fa429_add_simulation_carbon_report_support.py` (Line null) — Copilot

`carbon_project_id` is introduced as nullable, but later repository queries (e.g., `list_by_unit`/`get_by_unit_and_year`) inner-join `carbon_projects`, which will hide all existing CarbonReports with `carbon_project_id IS NULL`. This migration needs a data backfill: create the Calculator `carbon_projects` rows and populate `carbon_reports.carbon_project_id` for existing reports (then consider making it NOT NULL).

```suggestion
        """
        INSERT INTO carbon_projects (unit_id, start_year, end_year, name, is_public)
        SELECT
            cr.unit_id,
            MIN(cr.year) AS start_year,
            MAX(cr.year) AS end_year,
            'Calculator' AS name,
            false AS is_public
        FROM carbon_reports AS cr
        WHERE cr.carbon_project_id IS NULL
        GROUP BY cr.unit_id
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE carbon_reports AS cr
        SET carbon_project_id = cp.id
        FROM carbon_projects AS cp
        WHERE cp.unit_id = cr.unit_id
          AND cp.name = 'Calculator'
          AND cr.carbon_project_id IS NULL;
        """
    )
    op.execute(
        """
```

---

### File: `backend/app/api/v1/carbon_report_module.py` (Line null) — Copilot

## `_resolve_is_simulator()` treats a request as “simulator” solely based on whether an Explore report exists for (unit_id, year). Once an Explore report is created, this will cause _all_ `/modules/{unit}/{year}/...` traffic (including normal Calculator pages) to read/write the Explore report instead of the Calculator report. Use an explicit server-side signal (e.g., `SIMULATION_MODE.get()` from the middleware, or separate endpoints) to select the simulator report only for simulation requests.

### File: `backend/app/api/v1/carbon_report_module.py` (Line 294) — Copilot

## `check_module_permission(..., is_simulator_report=True)` fully bypasses module permission checks, but these endpoints do not enforce unit membership separately. With the current `_resolve_is_simulator` logic, any authenticated user could access/edit another unit’s simulation data if an Explore report exists for that unit/year. Add an explicit unit-access check (similar to `_require_unit_access` in `carbon_report.py`) before relaxing module permissions.

### File: `backend/alembic/versions/2026_05_01_1417-030717c03bd0_add_simulation_carbon_reports.py` (Line null) — Copilot

This migration adds NOT NULL columns (`carbon_report_type`, `is_viewable_by_unit_members`) to `carbon_projects` without a `server_default`. If the table already contains rows (e.g., existing environments or local dev), the upgrade will fail. Add a temporary default/backfill step (e.g., default `carbon_report_type='Calculator'`, `is_viewable_by_unit_members=false`), then drop the defaults if needed.

```suggestion
            server_default=sa.text("'Calculator'"),
        ),
    )
    op.add_column(
        "carbon_projects",
        sa.Column(
            "is_viewable_by_unit_members",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "carbon_projects",
        "carbon_report_type",
        existing_type=sa.Enum(
            "Calculator",
            "Simulator_Explore",
            "Simulator_Plan",
            name="carbon_report_type_enum",
        ),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "carbon_projects",
        "is_viewable_by_unit_members",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
```

---

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/api/v1/carbon_report.py:77`** — `POST /carbon-reports/` has no unit-scope authorization; any authenticated user can create Calculator reports for arbitrary `unit_id` values. Fix: load `unit = await db.get(Unit, report.unit_id)` and call `require_unit_access(current_user, unit)` before the `service.create()` call (matching the pattern used by the list/get endpoints in the same file).

- [ ] **`backend/app/api/v1/carbon_report.py:155`** — `GET /{carbon_report_id}` has no unit-scope check; any authenticated user can enumerate reports by guessing IDs. Fix: after loading the report, resolve `unit = await db.get(Unit, report.unit_id)` and call `require_unit_access(current_user, unit)` before returning it. Note: the Copilot comment about the Explore endpoints lacking this check was wrong — both simulator explore endpoints already call `require_unit_access`.

- [ ] **`backend/app/services/data_entry_emission_service.py:263`** — `percentage_of_last_year` override silently never fires: `report` is only populated when `_get_year_from_data_entry()` returns `None`, but that helper always resolves the year for entries with a valid module chain, so `report` stays `None` in production and `_get_percentage_override_kg` is never reached. Fix: unconditionally load `report` (or refactor `_get_year_from_data_entry` to return `(year, report)`) so the `if report is not None:` guard at line 287 can actually trigger.

- [ ] **`backend/app/services/data_entry_emission_service.py:160`** — The prior-year `CarbonReport` lookup filters only by `(unit_id, year)`; once Simulator Explore reports exist for the same unit/year, `.one_or_none()` will raise `MultipleResultsFound`. Fix: join through `CarbonProject` and add `CarbonProject.carbon_report_type == CarbonReportType.CALCULATOR` to the where clause (matching the scoping pattern already used in `carbon_report_repo.get_by_unit_and_year`).

### Data integrity

- [ ] **`backend/alembic/versions/2026_05_04_0945-05d68c9a6054_add_simulation_carbon_reports.py` + `backend/app/repositories/carbon_report_repo.py:57`** — `carbon_project_id` is added as nullable with no data backfill, but `list_by_unit()` and `get_by_unit_and_year()` inner-join `carbon_projects`, so all existing `carbon_reports` rows (where `carbon_project_id IS NULL`) become invisible after upgrade. Fix: add a migration step that creates one Calculator `CarbonProject` row per unit and populates `carbon_reports.carbon_project_id` for pre-existing rows before the inner-join queries go live.

### Maintainability / refactoring

- [ ] **`backend/app/services/carbon_report_module_service.py:356`** — CodeQL-flagged cyclic import: `carbon_report_service` imports `CarbonReportModuleService` at module level; `carbon_report_module_service` late-imports `CarbonReportService` to break the cycle. The late import is a band-aid, not a fix. Fix: extract the shared logic that both services need (e.g., report stat recomputation) into a standalone function in a lower-level module, removing the reverse dependency.

- [ ] **`frontend/src/stores/modules.ts:885`** — `getEmissionBreakdown` caches by `carbonReportId` alone; after `refreshEmissionBreakdownIfNeeded` refetches with `excludeModules=[]`, a subsequent call from `ResultsPage` with non-empty exclusions sees the cached ID match and returns the wrong (non-excluded) result. Fix: include a stable serialized `excludeModules` key alongside `carbonReportId` in the cache check, or have `refreshEmissionBreakdownIfNeeded` accept and forward the caller's exclude list.

---

### File: `backend/app/core/policy.py` (Line null) — Copilot

## When `is_simulator_report=True`, this function returns early and skips all authorization checks. Since simulator mode is currently derived from a client-controlled header, this effectively allows a caller to bypass module permissions (and any implicit unit scoping done by OPA). The simulator relaxation should still enforce unit access and must not trust a client signal as the source of truth.
