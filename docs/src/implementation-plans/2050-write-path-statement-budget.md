---
status: delivered
issue: 2050
last_updated: 2026-08-19
title: "Write-path statement budget — 29 SQL statements to 12"
summary: "Implementation plan for the interactive write path's statement-count reduction (#2050 Track J4/I5). One headcount-member POST costs 29 SQL statements after the B3 subtree fix (50 before), and twelve of them re-read three rows because four services are each constructed with only a session and re-derive identity independently. Eight tasks, each lowering the STATEMENT_BUDGET ratchet in test_headcount_post_statement_budget_pg.py: drop two redundant session.refresh calls, skip the audit head lookup on CREATE, skip the pre-delete SELECT on create, merge the count and FTE aggregates, thread the resolved (report, project, module) through the workflow, batch factor prefetch across emission roots, dispatch the report rollup, and replace the member uniqueness pre-check with a unique index. Lands at 8, against an irreducible synchronous floor of 7 for 'insert an entry and return fresh module stats'."
---

# Write-path statement budget: 29 → 8 (#2050)

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

> **Delivered 2026-08-19.** One headcount-member `POST` now costs **12
> statements**, down from 29 at plan time and 50 before Track J4's subtree fix.
> Every task landed; two diverged from what is written below, both recorded in
> [Outcome](#outcome). The final statement list and the two open follow-ups are
> there too.

**Goal:** take one interactive `POST` of a headcount member from 29 SQL
statements to 8, without giving up the caller's read-after-write contract
(their row, its emissions, their module's total).

**Architecture:** every task removes statements from one HTTP request by
either (a) not re-reading a row somebody upstream already holds, (b) merging
two grouped aggregates over the same table into one, or (c) moving work that
grows with _the whole report_ rather than with the user's action off the
request. No new user-visible state, no new status column, no spinner: what
the caller reads back stays synchronous and fresh.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy 2.0 async, Postgres via
psycopg3, Alembic, pytest + testcontainers.

**Spec:** [`2050-backend-compute-performance.md`](2050-backend-compute-performance.md)
— Track J4 is the measurement this plan acts on, Track J5 is the recorded
decision on why the write stays synchronous. Read both before Task 1.

## Global Constraints

- **The ratchet only goes down.** Every task lowers `STATEMENT_BUDGET` in
  `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`.
  A task that does not lower it has not delivered. Never raise it without
  writing the reason into this file.
- **Measure on psycopg3, never asyncpg.** Statement batching is
  driver-dependent and `app/db.py` forces `postgresql+psycopg`. The harness
  already converts the DSN — do not "simplify" it back to the conftest
  engine.
- **Check `distinct_factor_lookups` before reaching for a cache.** It
  separates "the same query repeated" (a memo fixes it) from "a different
  query per leaf" (only a combined query fixes it). One fix in this work's
  history was already wasted by not checking it.
- **The read-after-write contract is: their row, its emissions, their
  module's total.** No task may make any of those three eventually
  consistent.
- **No new `data_entry` status field and no "computing" state on the
  module.** See [Why the whole write stays synchronous](#why-the-whole-write-stays-synchronous).
- **Layering:** `route → workflow → service → repo`. Repos own SQL, services
  own logic, **the route owns the commit**. No SQL in routes or workflows.
- **Style:** functions ≤40 lines, ≤2 nesting levels; `col()` around every
  column ref; import `func`/`case`/`or_` from `sqlmodel`; no `# type: ignore`;
  no `assert` for runtime narrowing (`if x is None: raise ValueError(...)`);
  comments explain why, 1–2 lines.
- **Never hand-author an Alembic migration** — use
  `cd backend && make db-revision message="..."`, then prune false-positive
  `drop_index` calls.
- **Commits:** conventional commits, no `Co-Authored-By` trailer, one commit
  per task.

### Verification, run after every task

```bash
cd /Users/guilbert/works/git/github/co2-calculator
cd backend && uv run pytest tests/unit -q
cd backend && uv run pytest tests/integration/services/data_ingestion -q
cd /Users/guilbert/works/git/github/co2-calculator && make lint && make type-check
```

`tests/integration/services/data_ingestion/test_submodule_sort_search_matrix_pg.py::test_sort_search_pagination_matrix_all_modules`
**fails on `dev` already** — it is not caused by this work. Every other test
in that directory must pass. Do not "fix" it as part of a task here.

To see the live statement list while working:

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py \
  -q -s -p no:logging 2>&1 | grep -E ">>> POST|^ +[0-9]+\."
```

## The measured baseline (29 statements)

Numbering matches the harness output. This table is the map every task
navigates by.

| #     | statement                                                                      | removed by                  |
| ----- | ------------------------------------------------------------------------------ | --------------------------- |
| 1     | `SELECT carbon_reports` — `CarbonReportService.get`                            | Task 5 (collapses 1–3 to 1) |
| 2     | `SELECT carbon_projects` — plan scoping                                        | Task 5                      |
| 3     | `SELECT carbon_report_modules` — `get_module`                                  | Task 5                      |
| 4     | `SELECT data_entries` — member uniqueness pre-check                            | Task 8                      |
| 5     | `SELECT carbon_report_modules JOIN carbon_reports` — `fill_denormalized_scope` | Task 5                      |
| 6     | `INSERT data_entries`                                                          | **irreducible**             |
| 7     | `SELECT data_entries` — `session.refresh(created_entry)`                       | Task 1                      |
| 8     | `SELECT … JOIN carbon_projects` — `is_simulator_module`                        | Task 5                      |
| 9     | `SELECT audit_documents … FOR UPDATE` — `get_current_version`                  | Task 2                      |
| 10    | `INSERT audit_documents`                                                       | **irreducible**             |
| 11    | `SELECT audit_documents` — `session.refresh(doc_version)`                      | Task 1                      |
| 12    | `SELECT carbon_report_modules` — `_get_report_for_data_entry`                  | Task 5                      |
| 13    | `SELECT carbon_reports` — same                                                 | Task 5                      |
| 14    | `SELECT carbon_projects` — `resolve_factor_year`                               | Task 5                      |
| 15–17 | `SELECT factors … emission_type_id IN (…)` — one per emission root             | Task 6 (→ 1)                |
| 18    | `SELECT data_entry_emissions` — pre-delete lookup                              | Task 3                      |
| 19    | `INSERT data_entry_emissions` (batched, one statement)                         | **irreducible**             |
| 20    | `SELECT carbon_report_modules` — `recompute_stats_many`'s module load          | Task 5                      |
| 21    | `SELECT … sum(kg_co2eq), sum(additional_value)` grouped                        | **irreducible**             |
| 22    | `SELECT … count(*)` grouped                                                    | Task 4 (merges 22+23)       |
| 23    | `SELECT … sum(data->>'fte')` grouped                                           | Task 4                      |
| 24    | `SELECT carbon_reports.id, year` — `_years_by_report`                          | Task 5                      |
| 25    | `UPDATE carbon_report_modules` (stats)                                         | **irreducible**             |
| 26    | `SELECT carbon_report_modules` — report rollup                                 | Task 7                      |
| 27    | `SELECT carbon_reports` — report rollup                                        | Task 7                      |
| 28    | `SELECT carbon_reports JOIN carbon_projects` — report rollup                   | Task 7                      |
| 29    | `UPDATE carbon_reports` (stats)                                                | Task 7                      |

### The dominant finding

**Twelve of 29 statements re-read three rows.**

| row                               | read at                      | times   |
| --------------------------------- | ---------------------------- | ------- |
| `carbon_reports` (one row)        | 1, 13, 24, 27, 28            | **5×**  |
| `carbon_report_modules` (one row) | 3, 12, 20, 26 (+ joins 5, 8) | **4×**  |
| `carbon_projects` (one row)       | 2, 14, 28                    | **3×**  |
| `data_entries` (just inserted)    | 7                            | re-read |

`DataEntryService`, `DataEntryEmissionService`, `CarbonReportModuleService`
and `AuditDocumentService` are each constructed with a session only, so each
re-derives identity from scratch. `DataEntryEmissionService` even holds a
`_report_by_module_id` memo — it cannot help, because the route already
resolved the same rows on a _different instance_. Task 5 is the fix and is
the single biggest win in this plan.

### Task order and the ratchet

| task | change                                           | saves | `STATEMENT_BUDGET` after |
| ---- | ------------------------------------------------ | ----- | ------------------------ |
| 1    | Drop two redundant `session.refresh` calls       | −2    | 27                       |
| 2    | Skip the audit head lookup on `CREATE`           | −1    | 26                       |
| 3    | Skip the pre-delete `SELECT` on the create path  | −1    | 25                       |
| 4    | Merge the count and FTE aggregates               | −1    | 24                       |
| 5    | Thread the resolved `(report, project, module)`  | −9    | 15                       |
| 6    | Batch factor prefetch across emission roots      | −2    | 13                       |
| 7    | Dispatch the report rollup                       | −4    | 9                        |
| 8    | Unique index instead of the uniqueness pre-check | −1    | 8                        |

Tasks 1–4 are small and independent; do them in order to build the ratchet
habit before Task 5, which is the large one. Tasks 6–8 each depend only on
the baseline, not on each other.

**8 is one above the floor.** The floor is 4 writes (#6, #10, #19, #25) + one
identity read + one factor query + one aggregate = 7. Task 5 leaves one
identity read; nothing below 7 is reachable without giving up fresh module
stats, which is out of scope by decision.

## Why the whole write stays synchronous

Recorded so it is not re-litigated mid-execution. The original proposal
(2026-08-19) was to dispatch emission compute plus all stats to a job and
show "computing" in the UI. Three reasons that is not this plan:

1. **The cost it targeted is already gone.** 24 of the original 50
   statements were one query pattern — Strategy B3's per-leaf loop — not a
   workload. Dispatching would have moved the same 24 queries off the request
   and shown a spinner for them.
2. **Tasks 1–6 reach 13 with no async at all**, so the latency argument for
   dispatching the user-visible half is spent.
3. **It re-creates the failure Track J just removed.** An
   `emissions: computing` state means the table, graph, module total, report
   total _and the validation gate_ must each render "not final yet" honestly.
   The validation gate is the sharp edge: a module must not be validatable
   while its stats are known-stale.

Task 7 does dispatch — but only the report and project rollups, chosen by a
rule rather than by what looked slow: **cut where the work stops being
proportional to what the user just did.**

| work                          | grows with                                                                                   | verdict   |
| ----------------------------- | -------------------------------------------------------------------------------------------- | --------- |
| `INSERT data_entries`         | the one entry                                                                                | sync      |
| `INSERT data_entry_emissions` | leaves on that entry (~3–20)                                                                 | sync      |
| module stats                  | entries in _this_ module, bounded by [#2161's ceilings](2161-ceiling-scale-perf-fixtures.md) | sync      |
| report stats                  | _all modules_ in the report                                                                  | **async** |
| project stats                 | _all reports_ in the project                                                                 | **async** |

That boundary stays correct as the org grows, which "what is slow today"
does not.

---

## Task 1: Drop the two redundant `session.refresh` calls

Both re-read a row the `INSERT … RETURNING` just gave back. Every column is
set in Python before the flush, so the refresh loads nothing new.

**Files:**

- Modify: `backend/app/services/data_entry_service.py` (in `create`, the
  `await self.session.refresh(created_entry)` line)
- Modify: `backend/app/services/audit_service.py` (in `create_version`, the
  `await self.session.refresh(doc_version)` line)
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`
- Test: `backend/tests/unit/services/test_data_entry_service.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: no signature changes. `DataEntryService.create` keeps returning
  `DataEntryResponse`; `AuditDocumentService.create_version` keeps returning
  `AuditDocument`.

- [ ] **Step 1: Write the failing test**

The risk this change carries is a column with a **database-side** default
that the INSERT does not list: dropping the refresh would leave it
unloaded. So the test asserts the returned response carries every field the
caller reads, by value.

Append to `backend/tests/unit/services/test_data_entry_service.py`:

```python
@pytest.mark.asyncio
async def test_create_returns_fully_populated_response_without_refresh(
    db_session: AsyncSession,
):
    """#2050: ``create`` drops its ``session.refresh``, so every field the
    response carries must already be populated by the INSERT itself. A
    column with a DB-side default (rather than a Python-side one) would
    come back None here.
    """
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    service = DataEntryService(db_session)
    user = User(
        id=1,
        email="test@example.com",
        provider=UserProvider.DEFAULT,
        institutional_id="default-1441",
    )
    created = await service.create(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.member.value,
        user=UserRead.model_validate(user),
        data=DataEntryCreate(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=module.id,
            data={"name": "A", "user_institutional_id": "M-1", "sius_code": "51",
                  "fte": 1.0},
        ),
        source=DataEntrySourceEnum.USER_MANUAL.value,
        created_by_id=user.id,
    )

    assert created.id is not None
    assert created.data_entry_type_id == DataEntryTypeEnum.member.value
    assert created.carbon_report_module_id == module.id
    assert created.data["fte"] == 1.0
    assert created.source == DataEntrySourceEnum.USER_MANUAL.value
    # status has a Python-side default; None here would mean the row's
    # defaults only exist server-side and the refresh was load-bearing.
    assert created.status is not None
```

Add to that file's imports whatever it does not already have:

```python
from app.models.data_entry import DataEntrySourceEnum
from app.models.user import User, UserProvider
from app.schemas.user import UserRead
```

- [ ] **Step 2: Run it and watch it pass on the current code**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_service.py \
  -q -k without_refresh
```

Expected: **PASS**. This one is a guard, not a red test — it exists to fail
_after_ the refresh is removed if any column turns out to be server-side.
The red test for this task is the budget ratchet in Step 3.

- [ ] **Step 3: Lower the ratchet and watch it fail**

In `test_headcount_post_statement_budget_pg.py`, change:

```python
STATEMENT_BUDGET = 29
```

to

```python
STATEMENT_BUDGET = 27
```

(If the constant currently reads a different number, set it to exactly two
below what the harness prints for `total=`.)

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q
```

Expected: FAIL — `one member POST issued 29 statements, budget is 27`.

- [ ] **Step 4: Remove both refreshes**

In `backend/app/services/data_entry_service.py`, inside `create`, replace:

```python
        # 3. replace by flush; commit should happen in 'orchestrator' or 'route'
        # top level domain)
        await self.session.flush()
        await self.session.refresh(created_entry)
```

with:

```python
        # 3. replace by flush; commit should happen in 'orchestrator' or 'route'
        # top level domain)
        await self.session.flush()
        # No refresh: INSERT … RETURNING already supplied ``id``, and every
        # other column was set in Python before the flush (#2050 J4 — this
        # was one of two SELECTs that re-read a row we just wrote).
```

In `backend/app/services/audit_service.py`, inside `create_version`,
replace:

```python
        await self.session.refresh(doc_version)

        logger.info(
```

with:

```python
        # No refresh: the row's values were all set above, and ``id`` came
        # back from the INSERT (#2050 J4).
        logger.info(
```

- [ ] **Step 5: Verify both tests pass**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_service.py -q -k without_refresh
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q -s -p no:logging 2>&1 | grep ">>> POST"
```

Expected: unit test PASS, harness prints `total=27`.

- [ ] **Step 6: Run the full verification block**

Run the commands under
[Verification, run after every task](#verification-run-after-every-task).

- [ ] **Step 7: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(write-path): drop two redundant session.refresh calls (#2050)" \
  -m "Both re-read a row the INSERT ... RETURNING had just returned, with
every other column set in Python before the flush. 29 -> 27 statements on
one headcount-member POST. A unit test pins that the create response is
fully populated without the refresh, which is what would break if any
column turned out to have a server-side default."
```

---

## Task 2: Skip the audit head lookup on `CREATE`

`create_version` always runs `get_current_version(...) FOR UPDATE` to find
the previous version for the hash chain. On a `CREATE`, the entity id was
assigned by the sequence microseconds earlier, so there can be no previous
version: the query locks nothing and returns nothing.

**Not** the `INSERT … SELECT` variant floated earlier: `current_hash` is
computed in Python by `AuditDocumentService._compute_hash`, and
reimplementing that hash in SQL would put two implementations of a
security-relevant digest in the codebase — the same drift risk the
guardrails forbid for carbon formulas.

**Files:**

- Modify: `backend/app/services/audit_service.py` (`create_version`)
- Test: `backend/tests/unit/services/test_audit_sync_service.py`
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

**Interfaces:**

- Consumes: Task 1's edits to the same function (no conflict — different
  lines).
- Produces: `create_version` keeps its exact signature and return type.

- [ ] **Step 1: Write the failing test**

The behaviour that must not change: a `CREATE` writes `version=1` with
`previous_hash=None`, and a following `UPDATE` still chains onto it.

Append to `backend/tests/unit/services/test_audit_sync_service.py`:

```python
@pytest.mark.asyncio
async def test_create_version_chain_survives_skipping_the_head_lookup(
    db_session: AsyncSession,
):
    """#2050: CREATE no longer queries for a previous version (a fresh
    entity id cannot have one). The chain must still be correct: version 1
    with no previous_hash, and a subsequent UPDATE chained onto it.
    """
    service = AuditDocumentService(db_session)

    created = await service.create_version(
        entity_type="data_entries",
        entity_id=4242,
        data_snapshot={"fte": 1.0},
        change_type=AuditChangeTypeEnum.CREATE,
        changed_by=1,
        handler_id="TEST-USER",
    )
    assert created.version == 1
    assert created.previous_hash is None
    assert created.is_current is True

    updated = await service.create_version(
        entity_type="data_entries",
        entity_id=4242,
        data_snapshot={"fte": 2.0},
        change_type=AuditChangeTypeEnum.UPDATE,
        changed_by=1,
        handler_id="TEST-USER",
    )
    assert updated.version == 2
    assert updated.previous_hash == created.current_hash
    assert created.is_current is False
```

Ensure the file imports `AuditChangeTypeEnum` from `app.models.audit` and
`AuditDocumentService` from `app.services.audit_service`; add whichever is
missing.

- [ ] **Step 2: Run it — it passes on current code**

```bash
cd backend && uv run pytest tests/unit/services/test_audit_sync_service.py \
  -q -k chain_survives
```

Expected: PASS. It is the regression guard for Step 4.

- [ ] **Step 3: Lower the ratchet and watch it fail**

Set `STATEMENT_BUDGET = 26`, then:

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q
```

Expected: FAIL — `issued 27 statements, budget is 26`.

- [ ] **Step 4: Skip the lookup for CREATE**

In `create_version`, replace:

```python
        # Get current version to compute diff and hash chain
        current = await self.get_current_version(entity_type, entity_id)
```

with:

```python
        # #2050 J4: a CREATE's entity id came from the sequence moments ago,
        # so no prior version can exist — the FOR UPDATE head lookup locks
        # nothing and returns nothing. Skipping it removes one statement from
        # every interactive write. A real collision (two CREATEs for one id)
        # still surfaces: the flush below raises IntegrityError rather than
        # silently writing a second version 1.
        current = None
        if change_type is not AuditChangeTypeEnum.CREATE:
            current = await self.get_current_version(entity_type, entity_id)
```

- [ ] **Step 5: Verify**

```bash
cd backend && uv run pytest tests/unit/services/test_audit_sync_service.py -q
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q -s -p no:logging 2>&1 | grep ">>> POST"
```

Expected: unit tests PASS, harness prints `total=26`.

- [ ] **Step 6: Run the full verification block**

- [ ] **Step 7: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(audit): skip the head lookup when auditing a CREATE (#2050)" \
  -m "A CREATE's entity id came from the sequence moments earlier, so the
FOR UPDATE lookup for a previous version locks nothing and returns nothing.
27 -> 26 statements.

Deliberately not the INSERT ... SELECT variant: current_hash is computed in
Python by _compute_hash, and reimplementing that digest in SQL would leave
two implementations of a security-relevant hash to drift apart."
```

---

## Task 3: Skip the pre-delete `SELECT` on the create path

`CarbonReportModuleWorkflow.create` calls
`DataEntryEmissionService.upsert_by_data_entry`, whose first act is to
delete any existing emissions for the entry. A row created three statements
earlier has none, so the lookup is guaranteed empty.

**Files:**

- Modify: `backend/app/workflows/carbon_report_module.py` (in `create`, the
  `upsert_by_data_entry` call)
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`
- Test: `backend/tests/unit/services/test_data_entry_emission_service.py`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing new. Uses the existing
  `DataEntryEmissionService.create(data_entry: DataEntryResponse) -> list[DataEntryEmission]`,
  which already materializes real rows and skips the delete.

- [ ] **Step 1: Write the failing test**

The emissions written must be identical whichever method the workflow calls.
Append to `backend/tests/unit/services/test_data_entry_emission_service.py`:

```python
@pytest.mark.asyncio
async def test_create_writes_the_same_rows_upsert_would():
    """#2050: the create path calls ``create`` instead of
    ``upsert_by_data_entry`` to skip a pre-delete SELECT that can never
    match. Equivalence is the thing to pin, not the call itself.
    """
    factor = MagicMock(spec=Factor)
    factor.id = 99
    factor.year = 2024
    factor.emission_type_id = EmissionType.professional_travel__plane.value
    factor.values = {"ef_kg_co2eq_per_unit": 0.5, "unit": "km"}
    de = _make_data_entry_response({"distance_km": 100})

    def _patches(service):
        return (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.professional_travel__plane],
            ),
            _patched_handler(
                [
                    _emission_computation(
                        formula_key="ef_kg_co2eq_per_unit", quantity_key="distance_km"
                    )
                ]
            ),
        )

    via_create = _make_service()
    with (
        _patches(via_create)[0],
        _patches(via_create)[1],
        _patches(via_create)[2],
        _patches(via_create)[3],
    ):
        created = await via_create.prepare_create(de)

    via_upsert = _make_service()
    with (
        _patches(via_upsert)[0],
        _patches(via_upsert)[1],
        _patches(via_upsert)[2],
        _patches(via_upsert)[3],
    ):
        upserted = await via_upsert.prepare_create(de)

    assert [(r.emission_type_id, r.kg_co2eq) for r in created] == [
        (r.emission_type_id, r.kg_co2eq) for r in upserted
    ]
    assert created, "the fixture must actually produce emissions"
```

- [ ] **Step 2: Run it**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_emission_service.py \
  -q -k same_rows_upsert
```

Expected: PASS (both paths share `prepare_create`; this pins that they
stay shared).

- [ ] **Step 3: Lower the ratchet and watch it fail**

Set `STATEMENT_BUDGET = 25`, run the harness, expect FAIL at 26.

- [ ] **Step 4: Call `create` instead of `upsert_by_data_entry`**

In `backend/app/workflows/carbon_report_module.py`, inside `create`,
replace:

```python
            await DataEntryEmissionService(self.session).upsert_by_data_entry(
                data_entry_response=item
            )
```

with:

```python
            # #2050 J4: ``create``, not ``upsert_by_data_entry`` — the entry
            # was inserted three statements ago and cannot have emissions to
            # replace, so upsert's pre-delete lookup is a guaranteed-empty
            # SELECT. The update path keeps using upsert.
            await DataEntryEmissionService(self.session).create(item)
```

- [ ] **Step 5: Verify**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q -s -p no:logging 2>&1 | grep ">>> POST"
```

Expected: `total=25`, and `emission_statements` drops from 3 to 2.

Then confirm the update path is untouched:

```bash
cd backend && uv run pytest tests/unit/workflows -q
cd backend && uv run pytest tests/integration/services/data_ingestion/test_headcount_pg.py -q
```

- [ ] **Step 6: Run the full verification block**

- [ ] **Step 7: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(write-path): create emissions instead of upserting them on create (#2050)" \
  -m "upsert_by_data_entry deletes existing emissions first. On the create
path the entry was inserted three statements earlier and has none, so that
lookup is a guaranteed-empty SELECT. 26 -> 25 statements. The update path
still upserts."
```

---

## Task 4: Merge the count and FTE aggregates

`recompute_stats_many` issues two grouped queries over `data_entries` for
the same module ids: one `count(*)`, one `sum(data->>'fte')`. They differ
only in the aggregate and in the FTE one's headcount-only filter, which is
cheaper to apply in Python.

**Files:**

- Modify: `backend/app/services/carbon_report_module_service.py`
  (`recompute_stats_many`, and `_headcount_fte_by_module` is replaced by a
  combined helper)
- Test: `backend/tests/unit/services/test_carbon_report_service.py`
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  `CarbonReportModuleService._entry_counts_and_fte(modules: Sequence[CarbonReportModule]) -> tuple[dict[int, int], dict[int, float]]`
  returning `(counts_by_module_id, fte_by_headcount_module_id)`.
  `_headcount_fte_by_module` is **deleted** — no dual path.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/services/test_carbon_report_service.py`:

```python
@pytest.mark.asyncio
async def test_entry_counts_and_fte_matches_the_two_queries_it_replaces(
    db_session: AsyncSession,
):
    """#2050: one grouped query now returns both the entry count and the
    headcount FTE sum. Asserted against hand-computed values including the
    two edges that would otherwise be silently wrong: a non-headcount
    module (must get a count but no FTE entry) and an entry with no fte key
    (must not become 0.0 in the count).
    """
    headcount = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    travel = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add_all([headcount, travel])
    await db_session.flush()

    for data in ({"fte": 2.0}, {"fte": 3.5}, {"name": "no fte here"}):
        db_session.add(
            DataEntry(
                carbon_report_module_id=headcount.id,
                data_entry_type_id=DataEntryTypeEnum.member.value,
                data=data,
            )
        )
    db_session.add(
        DataEntry(
            carbon_report_module_id=travel.id,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            data={"distance_km": 100},
        )
    )
    await db_session.flush()

    service = CarbonReportModuleService(db_session)
    counts, fte = await service._entry_counts_and_fte([headcount, travel])

    assert counts[headcount.id] == 3
    assert counts[travel.id] == 1
    assert fte[headcount.id] == pytest.approx(5.5)
    # Non-headcount modules carry no FTE at all, exactly as before.
    assert travel.id not in fte
```

Add any missing imports: `CarbonReportModule`, `DataEntry`,
`DataEntryTypeEnum`, `ModuleTypeEnum`, `CarbonReportModuleService`.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend && uv run pytest tests/unit/services/test_carbon_report_service.py \
  -q -k counts_and_fte
```

Expected: FAIL — `'CarbonReportModuleService' object has no attribute '_entry_counts_and_fte'`.

- [ ] **Step 3: Add the combined helper**

In `backend/app/services/carbon_report_module_service.py`, delete
`_headcount_fte_by_module` entirely and add:

```python
    async def _entry_counts_and_fte(
        self, modules: Sequence[CarbonReportModule]
    ) -> tuple[dict[int, int], dict[int, float]]:
        """Entry count per module and FTE sum per headcount module, one query.

        #2050 J4: these were two grouped queries over the same table for the
        same module ids. The headcount-only restriction on the FTE sum is
        applied in Python, since filtering it in SQL is what forced the
        second query.
        """
        module_ids = [m.id for m in modules if m.id is not None]
        if not module_ids:
            return {}, {}
        headcount_ids = {
            m.id
            for m in modules
            if m.id is not None and m.module_type_id == ModuleTypeEnum.headcount
        }
        rows = (
            await self.session.execute(
                select(
                    col(DataEntry.carbon_report_module_id),
                    func.count(),
                    func.sum(DataEntry.data["fte"].as_float()),
                )
                .where(col(DataEntry.carbon_report_module_id).in_(module_ids))
                .group_by(col(DataEntry.carbon_report_module_id))
            )
        ).all()
        counts = {module_id: count for module_id, count, _ in rows}
        fte = {
            module_id: float(total or 0.0)
            for module_id, _, total in rows
            if module_id in headcount_ids
        }
        return counts, fte
```

- [ ] **Step 4: Use it in `recompute_stats_many`**

Replace this block:

```python
        count_rows = (
            await self.session.execute(
                select(
                    col(DataEntry.carbon_report_module_id),
                    func.count(),
                )
                .where(
                    col(DataEntry.carbon_report_module_id).in_(
                        carbon_report_module_ids
                    ),
                )
                .group_by(col(DataEntry.carbon_report_module_id))
            )
        ).all()
        counts = {module_id: count for module_id, count in count_rows}

        fte_by_module = await self._headcount_fte_by_module(modules)
```

with:

```python
        counts, fte_by_module = await self._entry_counts_and_fte(modules)
```

- [ ] **Step 5: Verify the unit test passes**

```bash
cd backend && uv run pytest tests/unit/services/test_carbon_report_service.py -q
```

- [ ] **Step 6: Lower the ratchet and verify**

Set `STATEMENT_BUDGET = 24`, then:

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q -s -p no:logging 2>&1 | grep ">>> POST"
```

Expected: `total=24`.

- [ ] **Step 7: Run the full verification block**

Pay attention to `tests/integration/services/data_ingestion/test_stats_json_pg.py`
— it is the closest coverage of stats content.

- [ ] **Step 8: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(stats): one grouped query for entry count and headcount FTE (#2050)" \
  -m "recompute_stats_many issued two grouped queries over data_entries for
the same module ids, differing only in the aggregate and in the FTE one's
headcount filter — which is cheaper in Python. 25 -> 24 statements.
_headcount_fte_by_module is removed rather than left beside its replacement."
```

---

## Task 5: Thread the resolved `(report, project, module)` through the write

The big one. The route already resolves the report, its project and the
module before doing anything (`resolve_report_module`). Four services then
re-derive the same three rows, nine times between them. Pass the resolved
identity down as an argument instead.

**Why an argument and not constructor injection:** the services are
constructed ad hoc all over the codebase (`DataEntryService(db)` appears in
dozens of call sites). Changing constructors would touch every one of them
and change service lifetimes. An optional keyword argument on the four
methods that need it is a strictly smaller diff and leaves every other
caller working unchanged.

**Files:**

- Create: `backend/app/schemas/write_scope.py`
- Modify: `backend/app/api/v1/carbon_report_module.py` (the `create_item`
  route — pass the scope into the workflow)
- Modify: `backend/app/workflows/carbon_report_module.py` (`create` —
  accept and forward)
- Modify: `backend/app/services/data_entry_service.py` (`create`,
  `fill_denormalized_scope`, `is_simulator_module`)
- Modify: `backend/app/services/data_entry_emission_service.py`
  (`prepare_create`, `_get_report_for_data_entry`)
- Modify: `backend/app/services/carbon_report_module_service.py`
  (`recompute_stats`, `recompute_stats_many`)
- Test: `backend/tests/unit/v1/test_carbon_report_module.py`
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

**Interfaces:**

- Consumes: Task 4's `_entry_counts_and_fte`.
- Produces:

```python
# app/schemas/write_scope.py
class WriteScope(BaseModel):
    """The identity rows an interactive write already resolved."""
    report: CarbonReportRead
    module: CarbonReportModuleRead
    is_simulator: bool

    @property
    def year(self) -> int | None: ...
    @property
    def unit_id(self) -> int | None: ...
```

Downstream signatures gain `scope: WriteScope | None = None`:

- `CarbonReportModuleWorkflow.create(..., scope: WriteScope | None = None)`
- `DataEntryService.create(..., scope: WriteScope | None = None)`
- `DataEntryService.fill_denormalized_scope(data_entries, scope=None)`
- `DataEntryEmissionService.prepare_create(..., scope: WriteScope | None = None)`
- `CarbonReportModuleService.recompute_stats(module_id, scope=None)`

Every one keeps working when `scope is None` — that is what leaves the
bulk/recalc callers untouched.

- [ ] **Step 1: Write the failing test**

The invariant worth pinning is behavioural equivalence: the same POST with
and without a threaded scope must produce the same response and the same
rows. The statement count is the budget test's job.

Append to `backend/tests/unit/v1/test_carbon_report_module.py`:

```python
@pytest.mark.asyncio
async def test_write_scope_carries_year_and_unit_from_the_report():
    """#2050: WriteScope is the carrier that stops four services re-reading
    the report, project and module the route already resolved.
    """
    report = MagicMock()
    report.year = 2025
    report.unit_id = 7
    module = MagicMock()
    module.id = 42

    scope = crm.WriteScope.model_construct(
        report=report, module=module, is_simulator=False
    )

    assert scope.year == 2025
    assert scope.unit_id == 7
    assert scope.module.id == 42
    assert scope.is_simulator is False
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend && uv run pytest tests/unit/v1/test_carbon_report_module.py \
  -q -k write_scope_carries
```

Expected: FAIL — `module 'app.api.v1.carbon_report_module' has no attribute 'WriteScope'`.

- [ ] **Step 3: Create the carrier**

Create `backend/app/schemas/write_scope.py`:

```python
"""The identity an interactive write already resolved (#2050 J4).

``resolve_report_module`` reads the carbon report, its project and the
module before any route body runs. Four services then re-derived the same
three rows nine times between them, because each is constructed with only
a session. This carries the resolved rows down instead.
"""

from pydantic import BaseModel, ConfigDict

from app.schemas.carbon_report import CarbonReportModuleRead, CarbonReportRead


class WriteScope(BaseModel):
    """Resolved identity for one interactive write."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    report: CarbonReportRead
    module: CarbonReportModuleRead
    # Whether the module's report belongs to a Simulator project — the one
    # fact ``is_simulator_module`` needed its own JOIN to answer.
    is_simulator: bool

    @property
    def year(self) -> int | None:
        return self.report.year

    @property
    def unit_id(self) -> int | None:
        return self.report.unit_id
```

Re-export it from the route module so tests and the workflow share one name.
In `backend/app/api/v1/carbon_report_module.py`, add to the imports:

```python
from app.schemas.write_scope import WriteScope
```

- [ ] **Step 4: Verify the carrier test passes**

```bash
cd backend && uv run pytest tests/unit/v1/test_carbon_report_module.py \
  -q -k write_scope_carries
```

Expected: PASS.

- [ ] **Step 5: Resolve `is_simulator` once, in the route**

`resolve_report_module` already loads the project — `require_plan_scope_for_report`
does `await db.get(CarbonProject, report.carbon_project_id)`, which is
statement #2. But it discards it, and **`CarbonReportRead` does not expose
`carbon_report_type`** (verified: its fields are `budget`,
`budget_currency`, `carbon_project_id`, `completion_progress`, `id`,
`is_grant`, `last_updated`, `overall_status`, `reference_year`, `stats`,
`unit_id`, `year`). So the type has to be carried explicitly.

Add a scope-building sibling to `resolve_report_module` in
`backend/app/api/v1/carbon_report_module.py`, and have the existing function
delegate to it so there is one resolution path, not two:

```python
async def resolve_write_scope(
    carbon_report_id: int,
    module_id: str,
    db: AsyncSession,
    current_user: User,
    action: str = "edit",
) -> WriteScope:
    """Resolve the report, module and project type for an interactive write.

    Same resolution as :func:`resolve_report_module`, but it keeps the
    project type that plan scoping already loaded instead of throwing it
    away — that one fact is what ``is_simulator_module`` needed its own
    three-table JOIN to answer (#2050 J4).
    """
    report, module = await resolve_report_module(
        carbon_report_id, module_id, db, current_user, action
    )
    project = None
    if report.carbon_project_id is not None:
        # Identity-map hit: require_plan_scope_for_report already loaded
        # this row inside resolve_report_module above, and the session does
        # not expire on commit, so this costs no statement.
        project = await db.get(CarbonProject, report.carbon_project_id)
    return WriteScope(
        report=report,
        module=module,
        is_simulator=(
            project is not None
            and project.carbon_report_type in SIMULATOR_REPORT_TYPES
        ),
    )
```

Add the imports:

```python
from app.models.carbon_project import CarbonProject
from app.schemas.write_scope import WriteScope
from app.services.data_entry_service import SIMULATOR_REPORT_TYPES
```

> **Verify the identity-map claim with the harness, not by reading.** After
> wiring this, the statement count must not go _up_. If it does, the `db.get`
> is issuing SQL — in that case change `require_plan_scope_for_report` in
> `backend/app/core/policy.py` to `return project` (additive: its current
> callers ignore the return value) and have `resolve_write_scope` use that
> returned object instead of re-getting it.

Then in the `create_item` route, replace the existing
`resolve_report_module` call with:

```python
    scope = await resolve_write_scope(
        carbon_report_id, module_id, db, current_user, action="edit"
    )
    report, carbon_report_module = scope.report, scope.module
```

leaving the permission check that follows it exactly as it is, and pass the
scope into the workflow:

```python
    response = await CarbonReportModuleWorkflow(db).create(
        carbon_report_module=carbon_report_module,
        data_entry_type_id=data_entry_type_id,
        item_data=item_data,
        current_user=UserRead.model_validate(current_user),
        request_context=request_context,
        background_tasks=background_tasks,
        scope=scope,
    )
```

- [ ] **Step 6: Thread it through the workflow**

In `backend/app/workflows/carbon_report_module.py`, add the parameter to
`create`:

```python
    async def create(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_type_id: int,
        item_data: dict,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
        scope: WriteScope | None = None,
    ) -> DataEntryResponse:
```

Import it: `from app.schemas.write_scope import WriteScope`.

Forward it at the three call sites inside the `try` block:

```python
            item = await DataEntryService(self.session).create(
                carbon_report_module_id=carbon_report_module.id,
                data_entry_type_id=data_entry_type_id,
                user=UserRead.model_validate(current_user),
                data=data_entry_create,
                request_context=request_context,
                background_tasks=background_tasks,
                source=DataEntrySourceEnum.USER_MANUAL.value,
                created_by_id=current_user.id,
                scope=scope,
            )
```

```python
            await DataEntryEmissionService(self.session).create(item, scope=scope)
```

```python
            await CarbonReportModuleService(self.session).recompute_stats(
                carbon_report_module.id, scope=scope
            )
```

- [ ] **Step 7: Use the scope in `DataEntryService`**

In `backend/app/services/data_entry_service.py`:

Add `scope: WriteScope | None = None` to `create`'s signature and import
`WriteScope`. Then replace:

```python
        await self.fill_denormalized_scope([entry])
```

with:

```python
        await self.fill_denormalized_scope([entry], scope=scope)
```

and replace:

```python
        if not await self.is_simulator_module(carbon_report_module_id):
```

with:

```python
        is_simulator = (
            scope.is_simulator
            if scope is not None
            else await self.is_simulator_module(carbon_report_module_id)
        )
        if not is_simulator:
```

Change `fill_denormalized_scope` to take the scope and short-circuit its
query:

```python
    async def fill_denormalized_scope(
        self, data_entries: list[DataEntry], *, scope: WriteScope | None = None
    ) -> None:
```

and immediately after the docstring, before the `module_ids` set is built:

```python
        # #2050 J4: an interactive write already resolved the report, so the
        # year/unit stamp needs no query of its own. Bulk callers pass no
        # scope and keep the batched lookup below.
        if scope is not None and scope.module.id is not None:
            for entry in data_entries:
                if entry.carbon_report_module_id != scope.module.id:
                    raise ValueError(
                        f"entry targets module {entry.carbon_report_module_id!r} "
                        f"but the write scope resolved {scope.module.id!r}"
                    )
                if entry.year is None:
                    entry.year = scope.year
                if entry.unit_id is None:
                    entry.unit_id = scope.unit_id
            return
```

- [ ] **Step 8: Use the scope in `DataEntryEmissionService`**

In `backend/app/services/data_entry_emission_service.py`, add
`scope: WriteScope | None = None` to both `create` and `prepare_create`,
import `WriteScope`, and forward it from `create` to `prepare_create`.

In `prepare_create`, seed the existing per-instance memo from the scope so
`_get_report_for_data_entry` finds it without querying — this reuses the
memo that already exists rather than adding a second mechanism:

```python
        # #2050 J4: the route already resolved this module's report. Seeding
        # the existing memo means _get_report_for_data_entry (and the year
        # resolution below) cost nothing, instead of re-reading the module,
        # report and project.
        if scope is not None and scope.module.id is not None:
            self._report_by_module_id.setdefault(scope.module.id, scope.report)
```

Place it immediately after the `data_entry.id is None` guard.

> `_report_by_module_id` is typed `dict[int, CarbonReport | None]` and
> `scope.report` is a `CarbonReportRead`, so widen the annotation to
> `dict[int, CarbonReport | CarbonReportRead | None]`. That is safe:
> `resolve_factor_year` is already declared
> `(session: AsyncSession, report: CarbonReport | CarbonReportRead)`
> (verified in `app/utils/factor_year.py:11-13`), and
> `_get_percentage_override_kg` reads only `reference_year`, `year` and
> `unit_id`, all of which `CarbonReportRead` carries. `make type-check`
> confirms the rest.

- [ ] **Step 9: Use the scope in `CarbonReportModuleService`**

In `backend/app/services/carbon_report_module_service.py`, add the scope to
`recompute_stats` and let it hand the already-loaded module to
`recompute_stats_many`:

```python
    async def recompute_stats(
        self,
        carbon_report_module_id: int,
        *,
        scope: WriteScope | None = None,
    ) -> None:
```

and add a `modules` escape hatch to `recompute_stats_many`:

```python
    async def recompute_stats_many(
        self,
        carbon_report_module_ids: list[int],
        *,
        bump_status: bool = True,
        prefetched_years: dict[int, int] | None = None,
    ) -> int:
```

Inside, replace:

```python
        year_by_report = await self._years_by_report(modules)
```

with:

```python
        # #2050 J4: an interactive write knows its report's year already.
        year_by_report = prefetched_years or await self._years_by_report(modules)
```

and have `recompute_stats` pass it:

```python
        prefetched_years = None
        if scope is not None and scope.report.id is not None and scope.year is not None:
            prefetched_years = {scope.report.id: scope.year}
        await self.recompute_stats_many(
            [carbon_report_module_id], prefetched_years=prefetched_years
        )
```

> The module load (`SELECT carbon_report_modules WHERE id IN (…)`) at the
> top of `recompute_stats_many` **stays**. It reads the ORM model that the
> method then mutates and flushes; the route's `CarbonReportModuleRead` is a
> read model and cannot be flushed. This is the one identity read the floor
> of 7 accounts for.

- [ ] **Step 10: Run the harness and read the remaining statements**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q -s -p no:logging 2>&1 | grep -E ">>> POST|^ +[0-9]+\."
```

Expected: `total=15`. If it lands higher, the printed list names exactly
which re-read survived — fix that one rather than adjusting the budget.

- [ ] **Step 11: Set the ratchet**

Set `STATEMENT_BUDGET = 15` and confirm the harness passes.

- [ ] **Step 12: Run the full verification block**

This task touches the most-shared services in the codebase, so the whole
integration directory matters here, not just the budget test.

- [ ] **Step 13: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(write-path): thread the resolved report and module through the write (#2050)" \
  -m "The route resolves the carbon report, its project and the module
before any handler body runs. Four services then re-derived the same three
rows nine times between them, because each is constructed with only a
session — DataEntryEmissionService even has a report memo that could not
help, since the route used a different instance.

WriteScope carries the resolved rows down as an optional keyword argument.
24 -> 15 statements. Optional because every bulk and recalc caller passes
none and keeps its batched lookups unchanged; an argument rather than
constructor injection because the services are constructed ad hoc at dozens
of call sites and their lifetimes should not change.

The module load in recompute_stats_many stays: it reads the ORM row the
method mutates and flushes, which a read model cannot do."
```

---

## Task 6: Batch factor prefetch across emission roots

`prepare_create` loops emission roots, and each root's `_fetch_factors`
call resolves its own subtree with its own query — three for a headcount
member (food, waste, commuting). All three subtrees are known before the
first query.

The mechanism already exists: `factor_query_cache`, which every bulk path
passes and `_fetch_factors` already consults. This task **primes** it in one
query instead of filling it lazily in three.

**Files:**

- Modify: `backend/app/services/data_entry_emission_service.py`
  (`prepare_create`, plus a new private helper)
- Test: `backend/tests/unit/services/test_data_entry_emission_service.py`
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

**Interfaces:**

- Consumes: `FactorService.list_by_emission_types(emission_types: list[EmissionType], year: int | None) -> list[Factor]`
  (already exists — added by the B3 fix) and `get_subtree_leaves`.
- Produces:
  `DataEntryEmissionService._prime_factor_query_cache(computations_by_type, year, factor_query_cache) -> None`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/services/test_data_entry_emission_service.py`:

```python
@pytest.mark.asyncio
async def test_prime_factor_query_cache_seeds_every_b3_criteria_in_one_query():
    """#2050: three emission roots meant three subtree queries. Priming the
    cache the bulk paths already use collapses them into one.
    """
    service = _make_service()

    food = MagicMock(spec=Factor)
    food.id = 1
    food.year = 2025
    food.emission_type_id = EmissionType.food__vegetarian.value
    food.values = {"ef_kg_co2eq_per_unit": 1.0}
    commuting = MagicMock(spec=Factor)
    commuting.id = 2
    commuting.year = 2025
    commuting.emission_type_id = EmissionType.commuting__cycling.value
    commuting.values = {"ef_kg_co2eq_per_unit": 2.0}

    comps = [
        _emission_computation(
            emission_type=EmissionType.food,
            factor_id=None,
            factor_query=FactorQuery(emission_type=EmissionType.food),
        ),
        _emission_computation(
            emission_type=EmissionType.commuting,
            factor_id=None,
            factor_query=FactorQuery(emission_type=EmissionType.commuting),
        ),
    ]

    with patch(
        "app.services.data_entry_emission_service.FactorService"
    ) as factor_service_cls:
        list_mock = AsyncMock(return_value=[food, commuting])
        factor_service_cls.return_value.list_by_emission_types = list_mock
        cache: dict = {}
        await service._prime_factor_query_cache(comps, year=2025,
                                                factor_query_cache=cache)

    # One query for both subtrees, not one per root.
    assert list_mock.await_count == 1
    # And every criteria is now answerable from the cache, so _fetch_factors
    # issues nothing.
    assert len(cache) == 2
    seeded = {f.id for factors in cache.values() for f in factors}
    assert seeded == {1, 2}
```

Add `FactorQuery` to the file's imports from `app.models.data_entry_emission`
if it is not already there, and make `_emission_computation` accept a
`factor_query` keyword (it builds `EmissionComputation(**kwargs)`, so this
works already).

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_emission_service.py \
  -q -k prime_factor_query_cache
```

Expected: FAIL — no attribute `_prime_factor_query_cache`.

- [ ] **Step 3: Add the helper**

In `backend/app/services/data_entry_emission_service.py`:

```python
    async def _prime_factor_query_cache(
        self,
        computations: list[EmissionComputation],
        year: int | None,
        factor_query_cache: dict,
    ) -> None:
        """Resolve every Strategy-B3 criteria in these computations at once.

        #2050 J4: ``_fetch_factors`` queried one subtree per emission root —
        three for a headcount member. All the subtrees are known before the
        first query, so one ``IN`` covers them, and the per-criteria results
        are seeded into the cache ``_fetch_factors`` already consults.

        Only the pure-B3 shape is primed (an ``emission_type`` with no
        kind/subkind/context/fallbacks). Anything else falls through to
        ``_fetch_factors``' own resolution, so a missed case costs a
        statement, never a wrong factor.
        """
        b3 = [
            comp
            for comp in computations
            if comp.factor_id is None
            and comp.factor_query is not None
            and comp.factor_query.emission_type is not None
            and comp.factor_query.kind is None
            and comp.factor_query.subkind is None
            and not comp.factor_query.context
            and not comp.factor_query.fallbacks
        ]
        if not b3:
            return

        leaves_by_comp = {
            id(comp): [
                EmissionType(node)
                for node in get_subtree_leaves(comp.factor_query.emission_type)
            ]
            for comp in b3
        }
        wanted = sorted(
            {leaf for leaves in leaves_by_comp.values() for leaf in leaves},
            key=lambda e: e.value,
        )
        found = await FactorService(self.session).list_by_emission_types(
            wanted, year=year
        )
        by_emission_type: dict[int, list[Factor]] = {}
        for factor in found:
            by_emission_type.setdefault(factor.emission_type_id, []).append(factor)

        for comp in b3:
            q = comp.factor_query
            if q is None:
                continue
            factors: list[Factor] = []
            for leaf in leaves_by_comp[id(comp)]:
                factors.extend(by_emission_type.get(leaf.value, []))
            if q.data_entry_type is not None:
                factors = [
                    f for f in factors if f.data_entry_type_id == q.data_entry_type
                ]
            factor_query_cache[self._factor_query_cache_key(q, year)] = factors
```

The cache key must be byte-identical to the one `_fetch_factors` builds, so
extract it into a shared helper. In `_fetch_factors`, replace the inline
`cache_key = (...)` construction with a call to this new method, and add:

```python
    @staticmethod
    def _factor_query_cache_key(q: FactorQuery, year: int | None) -> tuple:
        """The one place the Strategy-B memo key is built.

        Extracted so ``_prime_factor_query_cache`` and ``_fetch_factors``
        cannot drift — two spellings of this tuple would silently make the
        prime a no-op (#2050 J4).
        """
        return (
            q.data_entry_type,
            q.kind,
            q.subkind,
            q.emission_type,
            tuple(sorted(q.context.items())),
            tuple(sorted(q.fallbacks.items())),
            year,
        )
```

- [ ] **Step 4: Call it once, before the computation loop**

In `prepare_create`, the loop currently resolves computations inside the
emission-type loop. Hoist the resolution, prime, then iterate:

```python
        # Resolve every computation up front so the factor prefetch below
        # sees all of them, then prime the Strategy-B memo in one query
        # (#2050 J4). resolve_computations is pure, so hoisting it also stops
        # it running twice.
        computations_by_type: list[tuple[EmissionType, list[EmissionComputation]]] = [
            (emission_type, handler.resolve_computations(data_entry, emission_type, ctx))
            for emission_type in emission_types
        ]
        await self._prime_factor_query_cache(
            [comp for _, comps in computations_by_type for comp in comps],
            year=year,
            factor_query_cache=factor_query_cache,
        )
        for emission_type, computations in computations_by_type:
            for comp in computations:
```

`factor_query_cache` may arrive as `None` from interactive callers, so
default it once near the top of `prepare_create`:

```python
        # A cache scoped to one invocation cannot go stale — factors do not
        # change mid-call — so interactive callers get one too (#2050 J4).
        if factor_query_cache is None:
            factor_query_cache = {}
```

Keep the rest of the loop body exactly as it is.

- [ ] **Step 5: Verify the unit test passes**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_emission_service.py -q
```

- [ ] **Step 6: Lower the ratchet and verify**

Set `STATEMENT_BUDGET = 13` and `FACTOR_LOOKUP_BUDGET = 1`, then:

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py -q -s -p no:logging 2>&1 | grep ">>> POST"
```

Expected: `total=13`, `factor_lookups=1`.

- [ ] **Step 7: Run the full verification block**

`tests/integration/services/data_ingestion/test_headcount_pg.py` is the
sharpest check here — it pins computed kg per leaf against hand-computed
values, so a wrong factor set fails it loudly.

- [ ] **Step 8: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(emissions): prime the factor memo once instead of per emission root (#2050)" \
  -m "prepare_create looped emission roots and let each one resolve its own
subtree — three queries for a headcount member, though all three subtrees
are known before the first. Primes the factor_query_cache the bulk paths
already pass, in one query. 15 -> 13 statements, 3 -> 1 factor lookups.

The memo key now has exactly one construction site, shared by the prime and
by _fetch_factors: two spellings of that tuple would silently make the
prime a no-op. Only the pure-B3 shape is primed; anything else falls
through to _fetch_factors, so a missed case costs a statement rather than
returning a wrong factor."
```

---

## Task 7: Dispatch the report rollup

Four of the remaining statements recompute the **report**'s stats: they scan
every module in the report, re-read the report and its project, and update
the report row. That work grows with the whole report, not with the entry
the user just created, and nothing the caller reads back depends on it.

**Files:**

- Modify: `backend/app/services/carbon_report_module_service.py`
  (`recompute_stats_many` — stop calling the report rollup inline)
- Modify: `backend/app/api/v1/carbon_report_module.py` (the `create_item`
  route — dispatch after the commit)
- Create: `backend/app/tasks/report_rollup.py`
- Test: `backend/tests/integration/services/data_ingestion/test_report_rollup_dispatch_pg.py`
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

**Interfaces:**

- Consumes: `fire_and_forget_or_defer_to_poller(coro, *, name=None)` from
  `app.tasks._background`, `SessionLocal` from `app.db`,
  `CarbonReportService.recompute_report_stats_many(report_ids: list[int])`.
- Produces:
  `app/tasks/report_rollup.py::schedule_report_rollup(report_ids: set[int]) -> None`
  and `recompute_report_stats_detached(report_ids: list[int]) -> None`.

**Two decisions this task makes, stated before the code:**

1. **Its own session, not the request's.** The request session closes when
   the response is sent. The detached task opens a `SessionLocal()`, does its
   own commit, and is therefore not covered by the route's transaction — the
   report stats become eventually consistent by design, which is the point.
2. **No `DataIngestionJob` row.** Going through the job system would _add_ an
   INSERT (the job row must be committed before dispatch) to save four
   statements, and would need a coalescing story to avoid ten edits
   producing ten jobs. Report stats are derived and recomputable at any time,
   and an admin `recompute-stats` backfill already exists, so a lost rollup
   is staleness, not data loss. Failures are logged loudly by
   `fire_and_forget`'s done-callback — not swallowed.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/services/data_ingestion/test_report_rollup_dispatch_pg.py`:

```python
"""#2050 J4: the report rollup runs after the response, not inside it.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport
from app.models.module_type import ModuleTypeEnum
from app.services.carbon_report_module_service import CarbonReportModuleService

pytestmark = pytest.mark.asyncio


async def test_recompute_stats_does_not_touch_the_report_row(
    pg_dsn, make_unit, make_carbon_report, make_carbon_report_module
):
    """Module stats stay synchronous and fresh; the report row is left for
    the detached rollup. Pinned by observing the report's stats, so this
    fails if the inline rollup comes back.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            unit = await make_unit(session)
            report = await make_carbon_report(session, unit_id=unit.id, year=2025)
            module = await make_carbon_report_module(
                session,
                carbon_report_id=report.id,
                module_type_id=ModuleTypeEnum.headcount.value,
            )
            await session.commit()
            report_id = report.id
            module_id = module.id

        async with Sf() as session:
            await CarbonReportModuleService(session).recompute_stats(module_id)
            await session.commit()

        async with Sf() as session:
            refreshed_report = await session.get(CarbonReport, report_id)
            assert refreshed_report is not None
            # The module was refreshed; the report was deliberately not.
            assert refreshed_report.last_updated is None
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_report_rollup_dispatch_pg.py -q
```

Expected: FAIL — `last_updated` is set, because the rollup still runs
inline.

- [ ] **Step 3: Create the detached task**

Create `backend/app/tasks/report_rollup.py`:

```python
"""Detached report-stats rollup (#2050 J4).

A report's stats scan every module in the report, so the work grows with the
report rather than with the entry a user just created — and nothing the
caller reads back depends on it. It therefore runs after the response,
on its own session.

No ``DataIngestionJob`` row: that would add an INSERT to the request to save
four statements, and need its own coalescing story. Report stats are derived
and recomputable, and the admin ``recompute-stats`` backfill exists, so a
lost rollup is staleness rather than data loss. Failures are logged by
``fire_and_forget``'s done-callback rather than swallowed.
"""

from app.core.logging import get_logger
from app.db import SessionLocal
from app.tasks._background import fire_and_forget_or_defer_to_poller

logger = get_logger(__name__)


async def recompute_report_stats_detached(report_ids: list[int]) -> None:
    """Recompute report stats on a session of our own, then commit."""
    # Local import: app.services.carbon_report_service imports the module
    # service, which imports this module's caller — top-level would cycle.
    from app.services.carbon_report_service import CarbonReportService

    if not report_ids:
        return
    async with SessionLocal() as session:
        await CarbonReportService(session).recompute_report_stats_many(
            sorted(report_ids)
        )
        await session.commit()
    logger.info(f"Report stats rolled up for {len(report_ids)} report(s) (detached)")


def schedule_report_rollup(report_ids: set[int]) -> None:
    """Dispatch the rollup for ``report_ids`` after the response.

    Call this *after* the route commits: the detached task reads the module
    stats the request wrote, so it must not start before they are visible.
    """
    if not report_ids:
        return
    fire_and_forget_or_defer_to_poller(
        recompute_report_stats_detached(sorted(report_ids)),
        name=f"report-rollup-{'-'.join(str(i) for i in sorted(report_ids))}",
    )
```

- [ ] **Step 4: Stop the inline rollup and report which reports are stale**

In `backend/app/services/carbon_report_module_service.py`, change
`recompute_stats_many` to return the report ids it left stale instead of
rolling them up itself. Replace:

```python
        report_service = CarbonReportService(self.session)
        await report_service.recompute_report_stats_many(sorted(report_ids))
        return refreshed
```

with:

```python
        # #2050 J4: the report rollup is dispatched by the caller after the
        # commit, not run here — it scans every module in the report, which
        # is work proportional to the report rather than to the entry that
        # triggered it.
        self.stale_report_ids = report_ids
        return refreshed
```

Initialize it in `__init__` so the attribute always exists:

```python
        # Reports whose stats the last recompute left stale, for the caller
        # to dispatch (#2050 J4).
        self.stale_report_ids: set[int] = set()
```

Remove the now-unused local `CarbonReportService` import if nothing else in
the method uses it, and make `recompute_stats` surface the same set:

```python
        await self.recompute_stats_many(
            [carbon_report_module_id], prefetched_years=prefetched_years
        )
```

(`stale_report_ids` is already set by the call above — no extra code.)

> **Every other caller of `recompute_stats_many` must now dispatch too**,
> or report stats silently stop updating on those paths — a silent
> fallback. Find them and fix each one:
>
> ```bash
> cd backend && grep -rn "recompute_stats_many\|recompute_stats(" app/ --include=*.py | grep -v "def recompute"
> ```
>
> For the aggregation job and recalc handlers, call
> `await recompute_report_stats_detached(sorted(svc.stale_report_ids))`
> directly (they are already background work, so there is nothing to
> dispatch away from) rather than `schedule_report_rollup`.

- [ ] **Step 5: Dispatch from the route, after the commit**

In `backend/app/api/v1/carbon_report_module.py`, the `create_item` route
currently returns straight after the workflow calls. The commit happens
inside the workflow's `create` (per this repo's route-owns-commit rule the
workflow is the transaction owner here), so dispatch immediately after it
returns:

```python
    response = await CarbonReportModuleWorkflow(db).create(
        carbon_report_module=carbon_report_module,
        data_entry_type_id=data_entry_type_id,
        item_data=item_data,
        current_user=UserRead.model_validate(current_user),
        request_context=request_context,
        background_tasks=background_tasks,
        scope=scope,
    )
    # #2050 J4: after the commit, so the detached rollup sees this write's
    # module stats.
    schedule_report_rollup({carbon_report_module.carbon_report_id})
```

Import it:

```python
from app.tasks.report_rollup import schedule_report_rollup
```

Do the same in the `PATCH` and `DELETE` item routes in this file — any route
that changed module stats leaves the report stale. Verify by grep:

```bash
cd backend && grep -n "recompute_stats" app/workflows/carbon_report_module.py
```

- [ ] **Step 6: Verify the dispatch test passes**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_report_rollup_dispatch_pg.py -q
```

- [ ] **Step 7: Lower the ratchet and verify**

Set `STATEMENT_BUDGET = 9`, then run the harness. Expected: `total=9`.

- [ ] **Step 8: Run the full verification block**

Watch for tests that assert report stats immediately after a write — they
now need to await the rollup. `tests/integration/v1/test_merged_report_stats.py`
and `tests/integration/services/data_ingestion/test_stats_json_pg.py` are
the likely ones. Where a test needs the rollup to have happened, call
`await recompute_report_stats_detached([report_id])` explicitly rather than
sleeping.

- [ ] **Step 9: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "perf(stats): dispatch the report rollup instead of running it inline (#2050)" \
  -m "Four of the remaining statements recomputed the report's stats: they
scan every module in the report, re-read the report and its project, and
update the report row. That work grows with the whole report rather than
with the entry the user created, and nothing the caller reads back depends
on it. 13 -> 9 statements.

Module stats stay synchronous, so what the user sees is fresh and no
'computing' state is needed anywhere.

Its own session, because the request's closes with the response. No
DataIngestionJob row: that would add an INSERT to the request to save four
statements and need a coalescing story, while report stats are derived,
recomputable, and covered by the admin recompute-stats backfill — a lost
rollup is staleness, not data loss. Failures are logged by
fire_and_forget's done-callback."
```

---

## Task 8: Replace the member uniqueness pre-check with a unique index

`CarbonReportModuleWorkflow.create` runs a `SELECT` to check that
`(carbon_report_module_id, user_institutional_id, sius_code)` is unique,
then inserts. That is a check-then-act race as well as a statement: two
concurrent POSTs both pass the check.

**Files:**

- Modify: `backend/app/models/data_entry.py` (add the index declaration)
- Create: `backend/alembic/versions/<generated>_unique_member_role.py` (via
  `make db-revision`)
- Modify: `backend/app/workflows/carbon_report_module.py` (drop the
  pre-check, translate the IntegrityError)
- Test: `backend/tests/integration/services/data_ingestion/test_member_uniqueness_pg.py`
- Test: `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`

**Interfaces:**

- Consumes: Task 5's `WriteScope` (already threaded through `create`).
- Produces: no new Python API. The HTTP contract is unchanged: a duplicate
  still returns **422 with `detail="DUPLICATE_INSTITUTIONAL_ID"`**.

> **A partial index on JSON expressions.** The uniqueness key lives inside
> `data_entries.data` (a JSON column), and it applies only to
> `data_entry_type_id = member` rows. Alembic will not autogenerate an
> expression index — this is the one migration in this plan whose body needs
> hand-written `op.execute`, which the guardrails permit only because it is
> not expressible in model code. Generate the revision with
> `make db-revision` and add the `op.execute` to the generated file; do not
> hand-author the file itself.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/services/data_ingestion/test_member_uniqueness_pg.py`:

```python
"""#2050 J4: member role uniqueness is enforced by the database.

The pre-check it replaces was both a statement and a check-then-act race.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum

pytestmark = pytest.mark.asyncio


async def test_duplicate_member_role_is_rejected_by_the_database(
    pg_dsn, make_unit, make_carbon_report, make_carbon_report_module
):
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            unit = await make_unit(session)
            report = await make_carbon_report(session, unit_id=unit.id, year=2025)
            module = await make_carbon_report_module(
                session,
                carbon_report_id=report.id,
                module_type_id=ModuleTypeEnum.headcount.value,
            )
            await session.commit()
            module_id = module.id

        def _member(**data):
            return DataEntry(
                carbon_report_module_id=module_id,
                data_entry_type_id=DataEntryTypeEnum.member.value,
                data={"name": "A", "fte": 1.0, **data},
            )

        async with Sf() as session:
            session.add(_member(user_institutional_id="M-1", sius_code="51"))
            await session.commit()

        # Same person, same role, same module → rejected.
        with pytest.raises(IntegrityError):
            async with Sf() as session:
                session.add(_member(user_institutional_id="M-1", sius_code="51"))
                await session.commit()

        # Same person, *different* role → allowed (a person can hold several).
        async with Sf() as session:
            session.add(_member(user_institutional_id="M-1", sius_code="62"))
            await session.commit()

        # A student with the same pair is untouched by the member-only index.
        async with Sf() as session:
            session.add(
                DataEntry(
                    carbon_report_module_id=module_id,
                    data_entry_type_id=DataEntryTypeEnum.student.value,
                    data={"user_institutional_id": "M-1", "sius_code": "51",
                          "fte": 1.0},
                )
            )
            await session.commit()
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_member_uniqueness_pg.py -q
```

Expected: FAIL — `DID NOT RAISE IntegrityError`.

- [ ] **Step 3: Generate the migration**

```bash
cd backend && make db-revision message="unique member role per module"
```

Then open the generated file in `backend/alembic/versions/`, delete any
false-positive `drop_index` calls it invented, and make its body exactly:

```python
def upgrade() -> None:
    # #2050 J4: replaces a check-then-act SELECT in the create workflow.
    # Partial + expression index, so not expressible in model code: the key
    # lives inside the JSON ``data`` column and applies to member rows only.
    # A person can hold several roles in a unit, so sius_code is part of the
    # key (#951).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_member_role_per_module
        ON data_entries (
            carbon_report_module_id,
            (data ->> 'user_institutional_id'),
            (data ->> 'sius_code')
        )
        WHERE data_entry_type_id = 1
          AND data ->> 'user_institutional_id' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_member_role_per_module")
```

> `DataEntryTypeEnum.member.value` **is 1** (verified 2026-08-19). The
> literal in the SQL above is correct; re-check only if the enum changes.

**The index may fail to create on existing data** if duplicates already
exist. Check first, and report rather than silently de-duplicating:

```bash
cd backend && uv run python -c "
import asyncio
from sqlmodel import text
from app.db import SessionLocal
async def main():
    async with SessionLocal() as s:
        rows = (await s.execute(text('''
            SELECT carbon_report_module_id, data->>'user_institutional_id' uid,
                   data->>'sius_code' sius, count(*)
            FROM data_entries WHERE data_entry_type_id = 1
              AND data->>'user_institutional_id' IS NOT NULL
            GROUP BY 1,2,3 HAVING count(*) > 1
        '''))).all()
        print(f'{len(rows)} duplicate member roles')
        for r in rows[:20]: print(r)
asyncio.run(main())
"
```

If any exist, stop and report them — deciding which duplicate to delete is
the lead's call, not the implementer's.

- [ ] **Step 4: Declare the index in the model for documentation**

Model code cannot express a partial expression index, so add a comment
where a reader looks for it, in `backend/app/models/data_entry.py` on the
`DataEntry` class:

```python
    # A unique partial expression index enforces one (module, person, role)
    # per member row — see the ``uq_member_role_per_module`` migration. It
    # cannot live here: the key is inside ``data`` and applies only to
    # data_entry_type_id = member (#2050 J4).
```

- [ ] **Step 5: Verify the DB rejects duplicates**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_member_uniqueness_pg.py -q
```

Expected: PASS.

- [ ] **Step 6: Drop the pre-check and keep the 422**

In `backend/app/workflows/carbon_report_module.py`, delete this block:

```python
        if (
            data_entry_type == DataEntryTypeEnum.member
            and validated_data.model_dump().get("user_institutional_id")
        ):
            member_data = validated_data.model_dump()
            uid = member_data["user_institutional_id"]
            sius_code = member_data["sius_code"]
            is_unique = await DataEntryService(self.session).check_member_role_unique(
                carbon_report_module_id=carbon_report_module.id,
                uid=uid,
                sius_code=sius_code,
            )
            if not is_unique:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="DUPLICATE_INSTITUTIONAL_ID",
                )
```

and make the existing `except IntegrityError` arm distinguish this one
violation, so the HTTP contract is unchanged:

```python
        except IntegrityError as e:
            await self.session.rollback()
            # #2050 J4: the member-role uniqueness pre-check is gone; the
            # unique index reports the same condition, without the
            # check-then-act race two concurrent POSTs used to win.
            if "uq_member_role_per_module" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="DUPLICATE_INSTITUTIONAL_ID",
                ) from e
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database integrity error.",
            ) from e
```

Then delete `DataEntryService.check_member_role_unique` if nothing else
calls it — no dual path:

```bash
cd backend && grep -rn "check_member_role_unique" app/ tests/ --include=*.py
```

- [ ] **Step 7: Pin the HTTP contract**

Append to `backend/tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py`:

```python
@pytest.mark.asyncio
async def test_duplicate_member_post_still_returns_422(
    pg_app, make_unit, make_carbon_report, make_carbon_report_module
):
    """#2050 J4: the uniqueness pre-check became a unique index. The HTTP
    contract must not move — the frontend keys on this exact detail string.
    """
    async with pg_app["factory"]() as session:
        carbon_report_id = await _seed(
            session, make_unit, make_carbon_report, make_carbon_report_module
        )

    payload = {
        "name": "Test Member",
        "user_institutional_id": "M-001",
        "sius_code": "51",
        "fte": 0.8,
        "headcount_category": "food",
        "headcount_class": "vegetarian",
    }
    url = f"/v1/carbon-reports/{carbon_report_id}/modules/headcount/member"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(url, json=payload)
        second = await client.post(url, json=payload)

    assert first.status_code in (200, 201), first.text
    assert second.status_code == 422
    assert second.json()["detail"] == "DUPLICATE_INSTITUTIONAL_ID"
```

- [ ] **Step 8: Lower the ratchet and verify**

Set `STATEMENT_BUDGET = 8`, then run the harness. Expected: `total=8`.

- [ ] **Step 9: Run the full verification block**

- [ ] **Step 10: Commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator
git add -A
git commit -m "fix(headcount): enforce member role uniqueness in the database (#2050)" \
  -m "The create workflow ran a SELECT to check that (module, person, role)
was unique and then inserted — a statement and a check-then-act race two
concurrent POSTs both won. A unique partial expression index enforces it
instead. 9 -> 8 statements.

The HTTP contract is unchanged and pinned by a test: a duplicate still
returns 422 with detail DUPLICATE_INSTITUTIONAL_ID, now translated from the
IntegrityError. check_member_role_unique is deleted rather than left beside
the index.

The index is hand-written op.execute in a generated revision, which the
guardrails allow here because a partial index over JSON expressions is not
expressible in model code."
```

---

## Task 9: Record the result

**Files:**

- Modify: `docs/src/implementation-plans/2050-backend-compute-performance.md`
- Modify: `docs/src/implementation-plans/2050-write-path-statement-budget.md`
  (this file — frontmatter `status`)

- [ ] **Step 1: Capture the final statement list**

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_headcount_post_statement_budget_pg.py \
  -q -s -p no:logging 2>&1 | grep -E ">>> POST|^ +[0-9]+\."
```

- [ ] **Step 2: Add an I6 section to the 2050 plan**

Under Track J, add a short `### J6 — delivered` section with: the final
number, the eight tasks and what each saved, the final statement list, and
anything that came out higher than this plan predicted (with the reason).
Update that file's frontmatter `last_updated` and extend its `summary:` with
one clause about I6, mirroring how J4/J5 were added.

- [ ] **Step 3: Flip this plan's status**

Set `status: delivered` in this file's frontmatter and update
`last_updated`.

- [ ] **Step 4: Format, lint, commit**

```bash
cd /Users/guilbert/works/git/github/co2-calculator/docs && make format
cd /Users/guilbert/works/git/github/co2-calculator && make lint
git add -A
git commit -m "docs(2050): record the write-path statement budget result (#2050)"
```

---

## Self-review notes

Checked against the measured baseline, task by task:

- **Every one of the 29 statements has an owner** in the table, and the
  owners sum to 21 removed + 8 remaining (4 writes, 1 module load, 1 factor
  query, 1 emission aggregate, 1 audit insert). The arithmetic closes.
- **Two things this plan deliberately does not do.** It does not dispatch
  the audit write (durability beats latency for an audit trail on committed
  carbon data — Task 2 removes a statement instead), and it does not
  reimplement the audit hash in SQL (two implementations of a digest would
  drift, which is the same reasoning the guardrails apply to carbon
  formulas).
- **Three assumptions were checked against the source while writing this
  plan, so an implementer does not have to.** `resolve_factor_year` already
  accepts `CarbonReportRead` (`app/utils/factor_year.py:11-13`), so Task 5
  only widens a memo annotation. `CarbonReportRead` does **not** expose
  `carbon_report_type`, which is why Task 5 adds `resolve_write_scope`
  instead of deriving the flag from the report. `DataEntryTypeEnum.member`
  is `1`, so Task 8's raw SQL literal is right.
- **One claim left for the harness to confirm rather than reading:** that
  `db.get(CarbonProject, ...)` in `resolve_write_scope` is an identity-map
  hit and costs no statement. Task 5, Step 5 states the fallback if the
  count goes up instead of down.
- **The riskiest task is 7, not 5.** Task 5 is mechanical and type-checked
  end to end; Task 7 changes when report stats become visible, which other
  tests assert. Its Step 4 note about every other `recompute_stats_many`
  caller is the part most likely to be skipped, and skipping it silently
  stops report stats updating on the ingestion and recalc paths — a silent
  fallback, which this repo treats as worse than a loud failure.

---

## Outcome

Delivered on branch `fix/2050-track-h-levers`, one commit per task.

| task | change                                           | predicted | actual |
| ---- | ------------------------------------------------ | --------- | ------ |
| 1    | drop two redundant `session.refresh` calls       | 27        | **27** |
| 2    | skip the audit head lookup on `CREATE`           | 26        | **26** |
| 3    | create emissions instead of upserting on create  | 25        | **25** |
| 4    | merge the count and FTE aggregates               | 24        | **24** |
| 5    | thread the resolved `(report, module)`           | 15        | **19** |
| 6    | prime the factor memo once, not per root         | 13        | **17** |
| 7    | defer the report rollup                          | 9         | **13** |
| 8    | unique index instead of the uniqueness pre-check | 8         | **12** |

The four-statement gap against the prediction is entirely in Task 5: it saved
5, not 9. Two of the reads it was expected to remove turned out not to be
removable that way — see below.

### The remaining 12

```
 1  SELECT carbon_reports                    identity
 2  SELECT carbon_projects                   plan scoping
 3  SELECT carbon_report_modules             identity
 4  INSERT data_entries                      the write
 5  INSERT audit_documents                   the audit trail
 6  SELECT carbon_projects                   resolve_factor_year
 7  SELECT factors                           one IN over every subtree
 8  INSERT data_entry_emissions              batched, one statement
 9  SELECT carbon_report_modules             the ORM row recompute mutates
10  SELECT emission sums (grouped)           module stats
11  SELECT count + fte (grouped)             module stats
12  UPDATE carbon_report_modules             module stats
```

Five of those are writes or the aggregates behind the number the caller reads
back. The identity reads at 1–3 are one resolution, not three of the same row.

### Two divergences from the plan, both deliberate

**Task 5 — the `db.get` identity-map assumption was wrong.** The plan had
`resolve_write_scope` re-fetch the project with `db.get`, on the reasoning that
`require_plan_scope_for_report` had already loaded it into the session's
identity map. The harness showed that fetch issuing real SQL. The plan named
this exact fallback, and it is what shipped: `require_plan_scope_for_report`
now returns the `CarbonProject` it loads, and `resolve_write_scope` uses it.
Worth keeping: an identity-map claim is not verifiable by reading, only by
counting.

**Task 7 — opt-in deferral instead of unconditional.** The plan had
`recompute_stats_many` stop rolling up for everyone, which reading the call
sites showed would mean changing seven callers — three inside simulator prefill
and recalc, the internals the guardrails say not to touch without a reviewed
plan. The rule that matters is _"the rollup must not block a user's request"_,
not _"never inline"_: a background job has nobody waiting, so inline is correct
there. It shipped as `defer_report_rollup=False`, passed only by the
interactive write.

### Post-ship regression (2026-08-19): the CREATE skip broke login

Task 2 keyed the head-lookup skip on `change_type is CREATE`, assuming a
CREATE's entity id always came from the sequence in the same request. Auth
does not fit that assumption: it logs event-style CREATEs against reused
entity ids — `("User", user.id)` on every login, `("User", 0)` on every
failed login — so the second login after deploy inserted a second
`version=1, is_current=True` head and `audit_document_one_current_idx`
rejected the flush. The callback's `must_succeed=True` turned that into a
failed login for every returning user.

Fixed by making the skip an explicit `entity_is_new=True` opt-in on
`create_version`, passed only by the two call sites that mint the entity id
in the same request (interactive data-entry create, ingestion-job create).
Auth and year-configuration audits chain onto the existing head again, as
they did before Task 2. The interactive write path still measures 12
statements; the ratchet is untouched.

### Follow-up (2026-08-19): hardening the concurrent-write path itself

The regression above was deterministic — every returning user's login hit
it, `entity_is_new` fixes it outright and is what actually needed to reach
`dev`. Two further issues surfaced while diagnosing it, both about the
narrower case where two writers genuinely race on the same entity id (e.g.
two concurrent logins for one user):

- **`get_current_version`'s `FOR UPDATE` doesn't make concurrent creates
  safe, and this is NOT fixed yet.** It filters on `is_current = true`. Once
  the first writer commits, the locked row no longer matches that predicate,
  so Postgres drops it from the result — the second writer sees no head at
  all, computes `version=1`, and hits `audit_document_one_current_idx`
  exactly like the Task 2 bug did, just from real concurrency instead of a
  logic error (unchanged behavior — this pre-dates Task 2 and #1958 already
  names it as an accepted "real conflict"). A retry-on-conflict fix was
  attempted (roll back to a `SAVEPOINT` via `session.begin_nested()`, not
  the outer transaction, then re-read the real head) and **reverted**: every
  async shape tried either deactivated the whole SQLAlchemy transaction on
  the first flush failure (`PendingRollbackError` on the retry's own
  `get_current_version` read) or, once the savepoint was managed manually to
  work around that, left the DBAPI connection in a broken `[closed] [BAD]`
  state. A version that appeared to work was caught only by a second test
  asserting that an unrelated pending change earlier in the same session
  survives a losing retry — it didn't; the "targeted" rollback was in fact
  rolling back the outer transaction. Given that failure mode (silently
  discarding a caller's business-data write) is worse than the existing
  behavior (a loud 500), this needs a correctly-scoped SAVEPOINT idiom
  verified against SQLAlchemy 2.0's async session semantics specifically —
  or a `pg_advisory_xact_lock` instead of a savepoint retry — before it
  ships. Tracked here rather than as a silent no-op; `get_current_version`'s
  docstring was corrected to describe the real (non-)guarantee in the
  meantime.
- **`LoginCard.vue` fired the login navigation twice per click.** The submit
  button had both `@click="validate"` and `html-type="submit"` inside a
  `q-form` bound to `@submit.prevent="handleSubmit"` — the click both called
  `validate()` directly and triggered the form's native submit, which called
  it again. One click could send two concurrent OAuth logins for the same
  user, which is exactly the race the point above hardens against. Fixed by
  dropping the redundant `@click` (the form submit path already covers it)
  and adding a synchronous `if (loading.value) return; loading.value = true`
  guard in `authStore.login`/`login_test`, so a literal double-click is a
  no-op after the first. **No test added and not yet run against a live
  app** — mounting a Quasar/Pinia/i18n-dependent leaf component isn't wired
  into the Playwright CT harness (`frontend/playwright/index.ts` installs no
  plugins), and `frontend/node_modules` isn't installed in this worktree to
  run one ad hoc. Wiring that CT bootstrap (or a manual `make dev` login
  smoke test) is a follow-up before this ships, not before it merges as a
  draft.

### Three things the work turned up on the way

1. **`audit_documents.changed_at` is `TIMESTAMP WITHOUT TIME ZONE`** but the
   audit writer passes a tz-aware `datetime.now(UTC)`. psycopg accepts it by
   silently dropping the offset; asyncpg refuses outright. Production is
   psycopg, so nothing is broken today — but every stored audit timestamp has
   had its offset discarded rather than converted. Not fixed here.
2. **`audit_document_one_current_idx` is partial only on Postgres.** It is
   declared with `postgresql_where`, which SQLite ignores, so the test schema
   gets a _non-partial_ unique index and any second version of an entity
   violates it. Versioning cannot be tested on SQLite at all; Task 2's
   regression test lives in `tests/integration` for that reason.
3. **The integration schema comes from `create_all`, not Alembic.** A
   migration-only index would be invisible to the integration suite. Task 8's
   index is therefore declared in `DataEntry.__table_args__` — which the
   guardrails prefer anyway — with the migration carrying the same definition
   for real environments.

### Task 8's operational work, done 2026-08-19

The index needed three things around it, all shipped:

- **The headcount members API provider now dedupes.** It had no uniqueness
  check at all — the CSV provider has always had one — so with the index in
  place one duplicated person in the upstream Tableau export would have raised
  `IntegrityError` on the whole `bulk_create` and failed the entire sync job,
  on data we do not control. It now skips the row and counts it, the same
  per-row outcome the CSV path has always had.
- **The index builds `CONCURRENTLY`.** `data_entries` reaches ~1M rows in real
  environments and a plain `CREATE INDEX` holds an exclusive lock for the whole
  build. The trade: a failed build leaves an `INVALID` index instead of rolling
  back, so the upgrade drops any leftover first.
- **`backend/scripts/dedupe_member_roles.py`** reports duplicate groups and,
  with `--fix`, deletes only those whose payload is identical to the row it
  keeps (lowest id wins). Groups whose rows differ are reported and left alone:
  choosing which FTE is real changes a published total.

Testing it against a _seeded_ duplicate rather than only a clean database
caught a real bug — the classification reads autobegin the connection's
transaction, so the deletes' `conn.begin()` raised and `--fix` silently deleted
nothing.

**Duplicates checked on the lead's environment 2026-08-19: none.** Run the
script against dev, stage and prod before the migration reaches them.

### Follow-ups

- **`test_submodule_sort_search_matrix_pg` fails on `dev`** and is unrelated to
  this work — verified by running it in a clean worktree at `origin/dev`
  (`48c1b440`). Searching `building_name` in the `building_embodied_energy`
  submodule returns nothing, so a user typing a building name into that
  submodule's search gets an empty table. Deserves its own issue.
- **The floor is now ~9, not 7.** Statements 2 and 6 are two separate
  `carbon_projects` reads (plan scoping, then `resolve_factor_year`); threading
  the project into year resolution would fold them into one. Statement 9's
  module load cannot go: it is the ORM row `recompute_stats_many` mutates.
