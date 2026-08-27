---
status: delivered
issue: 2161
last_updated: 2026-08-18
summary: "Turn #2161's real per-data_entry_type ceiling estimates into a
  reusable Postgres fixture (one unit seeded at worst-case scale via the
  production recalc path, so factor resolution is real) and a systematically
  -discovered suite that hits every GET endpoint under app/api/v1 against it,
  asserting a 200ms ceiling-scale budget."
---

# Ceiling-scale performance fixtures (#2161)

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one Postgres fixture that seeds a single unit's calculator
report at #2161's real per-`DataEntryTypeEnum` ceiling counts, with emissions
computed through the actual production recalc path (not a placeholder), then
a pytest suite that discovers every GET route under `backend/app/api/v1`,
binds its path params from that fixture, and asserts each responds within a
ceiling-scale latency budget.

**Architecture:** A session-scoped Postgres testcontainer (mirrors
`tests/integration/services/data_ingestion/conftest.py`'s pattern, its own
container/port) holds one unit/report/module tree seeded once via
`seed_data_entries.py`'s COPY helpers, with real emissions computed by
calling `EmissionRecalculationWorkflow.recalculate_for_data_entry_type` once
per type — the same code production runs, so factor resolution, and
therefore `primary_factor_id`/enrichment cost on read, is real. Routes are
discovered from `app.routes` at collection time (not hand-listed), so a new
GET endpoint fails collection until it's given a binding or an exclusion.

**Tech Stack:** pytest, pytest-asyncio, httpx `AsyncClient` +
`ASGITransport`, asyncpg (COPY), SQLModel async engine, the existing
`docker`-python testcontainer pattern.

**Spec:** GitHub issue
[#2161](https://github.com/EPFL-ENAC/co2-calculator/issues/2161) (real
per-type ceilings from martina-gallato, 2026-08-18) and
`docs/src/implementation-plans/2050-backend-compute-performance.md` Track F4
(this plan's ceiling table is now the canonical source both files use — F4
was updated in the same session to point here instead of re-deriving the
numbers).

## Global Constraints

- Ceiling numbers are `docs/src/implementation-plans/2050-backend-compute-performance.md`
  Track F4's table verbatim — do not re-derive them; import or re-key off
  that single source (Task 1) so the two docs can't drift.
- Two separate latency budgets, two separate scopes — do not conflate them:
  **80ms locally / 400ms in dev** is the guardrails' normal-load budget
  (`docs/src/contributing/guardrails.md`, unrelated to this plan). **200ms**
  is this suite's budget, against #2161's worst-case ceiling data — a
  harsher scenario the guardrails' number was never meant to cover.
- No SQL in routes; this plan only _reads_ through existing routes/services,
  it adds no new endpoint.
- Backend is the source of truth: the fixture computes emissions via the
  real `EmissionRecalculationWorkflow`, never a hand-rolled shortcut formula.
- No silent fallbacks: a data entry type whose seeded payload doesn't
  resolve to a real emission is excluded **by name, with a one-line
  reason**, never silently zero-filled (mirrors Track C2's own exclusion of
  `process_emissions`/`plane`/`it` from its measurement for the same
  reason).
- This suite requires Docker (Postgres testcontainer) **and** real factor
  data from `backend/INPUT_DATA/*.csv` — gitignored, developer-supplied,
  the same precondition `make bootstrap-years` already has. No CSV under
  `INPUT_DATA/` is committed (verified: `git check-ignore` matches every
  file `seed_generic_factors.FACTOR_SEEDS` reads), and there is no CI step
  that provisions it — so unlike the other Docker-gated PG suites under
  `tests/integration/`, **this one cannot run in the daily
  `integration-tests.yml` workflow's fresh checkout** and must not be
  assumed to. It's a local, on-demand gate, same as Track C2/F0's own real
  profiling in 2050 ("done, on a local seed" — never run in CI either).
  Guard this explicitly (Task 3) with a clear skip, not a buried
  `FileNotFoundError` three layers down in `LocalFactorCSVProvider`.
- Per project convention: don't run the suite yourself once written — stop
  at `make lint` / `make type-check`. The user runs `pytest`.

**Why this matters, concretely:** `2050-backend-compute-performance.md`
Track H found a real 825ms production query on
`GET .../modules/{module_id}/{submodule_id}` — `planner_headcount` missing
from a fast-path type tuple, falling through to an unfiltered
`data_entry_emissions` aggregation. That route is a plain `/v1` GET with no
exclusion reason, so Task 4's route discovery already picks it up
automatically; this plan's ceiling-scale fixture (Task 3) is exactly the
kind of dataset that would have caught Track H's regression class before a
trace had to. Not a scope change — noted here as the suite's own
motivating case.

## Explicitly out of scope (follow-up, not this plan)

- **Planner ceilings** (`planner_headcount`/`planner_purchase`/
  `planner_purchase_budget`, and every `simulator_plan.py` GET). A
  `SimulatorPlan` + multi-year-reports tree is a structurally different
  fixture shape than one calculator `CarbonReport` — Track F's own PATCH
  work treats Calculator and Simulator Plan as separate trees throughout.
  Bolting both into one fixture here would blur two ceilings tests instead
  of building one cleanly. `simulator_plan.py`'s GET routes are excluded in
  Task 4 with this same reason; a second plan can lift the exclusion once
  someone sizes planner ceilings for real (today's 50/5,000/10 in F4 are the
  requester's own guesses, not martina's data).
- **`data_sync.py`'s streaming/job-status GETs** — excluded in Task 4
  (see the exclusion table); their cost is driven by
  ingestion-pipeline-row count, not `data_entries` count, which is a
  different ceiling question than #2161 asked.

---

### Task 1: Ceiling table as code

**Files:**

- Create: `backend/app/seed/ceilings.py`
- Test: `backend/tests/unit/seed/test_ceilings.py`

**Interfaces:**

- Produces: `CEILING_PER_UNIT_YEAR: dict[DataEntryTypeEnum, int]` (calculator
  types only — the 23 non-planner `DataEntryTypeEnum` members). `EXCLUDED_FROM_CEILING_FIXTURE: dict[DataEntryTypeEnum, str]`
  (data-entry types whose seeded payload is known not to resolve a real
  factor — populated for real in Task 3 once measured; starts empty here).
  `TOTAL_CEILING_PER_UNIT_YEAR: int` (sum of the dict's values, asserted by
  its own test to equal 21,050 so a future silent edit to one number is
  caught).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/seed/test_ceilings.py
"""Pins #2161's real per-data_entry_type ceilings against silent drift.

Source: docs/src/implementation-plans/2050-backend-compute-performance.md
Track F4, sourced from GitHub issue #2161 (martina-gallato, 2026-08-18).
"""

from app.models.data_entry import DataEntryTypeEnum
from app.seed.ceilings import CEILING_PER_UNIT_YEAR, TOTAL_CEILING_PER_UNIT_YEAR


def test_ceiling_covers_every_calculator_data_entry_type():
    calculator_types = {t for t in DataEntryTypeEnum if not t.is_planner_kind}
    assert set(CEILING_PER_UNIT_YEAR) == calculator_types


def test_ceiling_values_match_2050_track_f4():
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.member] == 500
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.train] == 5000
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.animal_facilities] == 50
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.purchases_centralized] == 1000


def test_total_ceiling_is_pinned():
    assert TOTAL_CEILING_PER_UNIT_YEAR == 21_050
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/seed/test_ceilings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed.ceilings'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/seed/ceilings.py
"""Real per-data_entry_type ceiling estimates (#2161).

Sourced from martina-gallato's comment on GitHub issue #2161 (2026-08-18) —
the only calculator-type row without a number was
``building_embodied_energy`` -> she flagged it as the (already-renamed)
``building_construction_renovation`` concept; kept under its current enum
name here since the model hasn't been renamed.

This is the single source of truth for the ceiling numbers. Track F4 in
``docs/src/implementation-plans/2050-backend-compute-performance.md`` quotes
this table rather than re-deriving it — keep both in sync if a number
changes here.
"""

from app.models.data_entry import DataEntryTypeEnum

CEILING_PER_UNIT_YEAR: dict[DataEntryTypeEnum, int] = {
    DataEntryTypeEnum.member: 500,
    DataEntryTypeEnum.student: 500,
    DataEntryTypeEnum.scientific: 1000,
    DataEntryTypeEnum.it: 1000,
    DataEntryTypeEnum.other: 1000,
    DataEntryTypeEnum.plane: 500,
    DataEntryTypeEnum.train: 5000,
    DataEntryTypeEnum.building: 500,
    DataEntryTypeEnum.energy_combustion: 500,
    DataEntryTypeEnum.building_embodied_energy: 500,
    DataEntryTypeEnum.external_clouds: 500,
    DataEntryTypeEnum.external_ai: 500,
    DataEntryTypeEnum.process_emissions: 500,
    DataEntryTypeEnum.scientific_equipment: 1000,
    DataEntryTypeEnum.it_equipment: 1000,
    DataEntryTypeEnum.consumable_accessories: 1000,
    DataEntryTypeEnum.biological_chemical_gaseous_product: 1000,
    DataEntryTypeEnum.services: 1000,
    DataEntryTypeEnum.vehicles: 1000,
    DataEntryTypeEnum.other_purchases: 1000,
    DataEntryTypeEnum.purchases_centralized: 1000,
    DataEntryTypeEnum.research_facilities: 500,
    DataEntryTypeEnum.animal_facilities: 50,
}

TOTAL_CEILING_PER_UNIT_YEAR = sum(CEILING_PER_UNIT_YEAR.values())

# Populated for real by Task 3 once a type is measured to bail out at zero
# emissions against the seeded factor set — mirrors Track C2's exclusion of
# process_emissions/plane/it from its own measurement for the identical
# reason. Empty until Task 3 runs the recalc and records what actually
# resolves; never silently skip a type without adding it here.
EXCLUDED_FROM_CEILING_FIXTURE: dict[DataEntryTypeEnum, str] = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/seed/test_ceilings.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/seed/ceilings.py backend/tests/unit/seed/test_ceilings.py
git commit -m "feat(seed): add #2161 real per-data_entry_type ceiling table"
```

---

### Task 2: Harness spike — HTTP + real Postgres + auth override, one endpoint

Prove the harness before building ten more tests on top of an assumption.
`GET /v1/units/{unit_id}/results` is the target: it's a plain read, no
recalculation side effect, and its latency is expected to scale with
`data_entries` count.

**Files:**

- Create: `backend/tests/integration/performance/__init__.py`
- Create: `backend/tests/integration/performance/conftest.py`
- Create: `backend/tests/integration/performance/test_harness_spike_pg.py`

**Interfaces:**

- Consumes: `seeded_year_with_units(session, *, year, n_units=1)` and
  `ensure_pipeline_for_job` from
  `tests.integration.services.data_ingestion.conftest` (already-established
  cross-package test import — see
  `tests/integration/services/data_ingestion/test_factors_year_scope_pg.py`
  for precedent).
- Produces: `perf_postgres_container` (session-scoped docker fixture),
  `perf_pg_dsn` (**session-scoped**, unlike `data_ingestion/conftest.py`'s
  function-scoped `pg_dsn` — this suite's fixture data is read-only across
  every test, so resetting the schema per test would re-seed ~21k rows for
  every parametrized case and make the suite unusable; say so in the
  docstring), `perf_session_factory` (session-scoped
  `async_sessionmaker`), `perf_app` (function-scoped: wires
  `app.dependency_overrides` to `perf_session_factory` + a fake user with
  every `backoffice.*`/`modules.*` permission, and monkeypatches
  `app.core.security.is_permitted` to always allow — mirrors
  `test_recompute_stats_endpoint_pg.py`'s `pg_app` fixture exactly, cleared
  after each test via `app.dependency_overrides.clear()`).

- [ ] **Step 1: Write the conftest (harness only, no seeding yet)**

```python
# backend/tests/integration/performance/conftest.py
"""Session-scoped Postgres fixture for ceiling-scale GET-endpoint timing.

Mirrors tests/integration/services/data_ingestion/conftest.py's
postgres_container/pg_dsn pattern, with one deliberate divergence:
perf_pg_dsn is SESSION-scoped, not function-scoped. Every test in this
suite reads the same ~21k-row ceiling fixture (Task 3) read-only; a fresh
drop_all/create_all + re-seed per test would dominate wall time and make
the suite unusable as a CI gate.
"""

import time

import docker
import docker.errors
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

PG_IMAGE = "postgres:16-alpine"
PG_CONTAINER_NAME = "test-performance-postgres"
PG_PORT = 55433
PG_DB = "test_performance"
PG_USER = "test"
PG_PASSWORD = "test"
PG_READY_MARKER = b"database system is ready to accept connections"


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.fixture(scope="session")
def perf_postgres_container(docker_client):
    container = None
    try:
        try:
            old = docker_client.containers.get(PG_CONTAINER_NAME)
            old.remove(force=True)
        except docker.errors.NotFound:
            pass

        try:
            docker_client.images.get(PG_IMAGE)
        except docker.errors.ImageNotFound:
            docker_client.images.pull(PG_IMAGE)

        container = docker_client.containers.run(
            image=PG_IMAGE,
            name=PG_CONTAINER_NAME,
            ports={"5432/tcp": PG_PORT},
            environment={
                "POSTGRES_DB": PG_DB,
                "POSTGRES_USER": PG_USER,
                "POSTGRES_PASSWORD": PG_PASSWORD,
            },
            detach=True,
            remove=True,
        )

        timeout = 60
        deadline = time.time() + timeout
        while time.time() < deadline:
            container.reload()
            if container.status == "running":
                if container.logs().count(PG_READY_MARKER) >= 2:
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError("Postgres container failed to become ready")

        url = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}"
        yield {"url": url, "container": container}
    finally:
        try:
            c = docker_client.containers.get(PG_CONTAINER_NAME)
            c.stop(timeout=10)
        except docker.errors.NotFound:
            pass


@pytest_asyncio.fixture(scope="session")
async def perf_pg_dsn(perf_postgres_container):
    """Session-scoped: schema created ONCE. See module docstring for why."""
    url = perf_postgres_container["url"]
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    await engine.dispose()
    yield url


@pytest_asyncio.fixture(scope="session")
async def perf_session_factory(perf_pg_dsn):
    engine = create_async_engine(perf_pg_dsn, future=True)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def perf_app(perf_session_factory, monkeypatch):
    """Wire the FastAPI app to the perf Postgres + bypass auth.

    Mirrors test_recompute_stats_endpoint_pg.py's pg_app fixture.
    """
    from unittest.mock import MagicMock

    import app.api.deps as deps_module
    import app.core.security as security_module
    from app.main import app

    async def override_get_db():
        async with perf_session_factory() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "perf-test@example.com"
    fake_user.institutional_id = "PERF-TEST-USER"
    fake_user.provider = 0
    fake_user.calculate_permissions = lambda: {"backoffice.pipeline_operations": ["view", "edit"]}

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: fake_user

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)

    yield app

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write the spike test**

```python
# backend/tests/integration/performance/test_harness_spike_pg.py
"""Proves the HTTP + real-Postgres + auth-override harness works end to end
before Tasks 3-5 build the ceiling fixture and the full endpoint sweep on
top of it. One endpoint, minimal seed, real timing number.
"""

import time

import httpx
import pytest

from tests.integration.services.data_ingestion.conftest import (
    seeded_year_with_units,
)

pytestmark = pytest.mark.asyncio


async def test_unit_results_endpoint_responds_with_real_pg(
    perf_app, perf_session_factory
):
    async with perf_session_factory() as session:
        seeded = await seeded_year_with_units(session, year=2025, n_units=1)
    unit_id = seeded.units[0].id

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=perf_app), base_url="http://test"
    ) as client:
        start = time.perf_counter()
        resp = await client.get(f"/v1/units/{unit_id}/results")
        elapsed_ms = (time.perf_counter() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms < 1000  # generous — this is the harness spike, not the budget
```

- [ ] **Step 3: Run it against real Docker**

Run: `cd backend && uv run pytest tests/integration/performance/test_harness_spike_pg.py -v`
Expected: PASS. If `get_current_active_user`/`is_permitted` don't cover this
route's actual permission gate, the failure will be a 403 — read the gate in
`app/api/v1/unit_results.py` and extend `fake_user.calculate_permissions`
accordingly; do not weaken the route's real permission check to make the
test pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/performance/
git commit -m "test(perf): spike the HTTP+real-PG+auth-override harness on one GET route"
```

---

### Task 3: Ceiling-scale seed fixture with real emission computation

This is the task the advisor flagged as make-or-break: seeded emissions must
resolve through the **real** factor-matching path, or every downstream
timing number measures a cheaper-than-production code path (GET handlers
join `primary_factor_id -> Factor` and read enrichment fields off it — see
2050's Track F3).

**Files:**

- Modify: `backend/app/seed/random_generator/seed_data_entries.py` (add one
  function, see below — everything else in that file is reused unmodified)
- Create: `backend/tests/integration/performance/fixtures.py`
- Test: `backend/tests/integration/performance/test_ceiling_fixture_pg.py`

**Interfaces:**

- Produces (in `seed_data_entries.py`):
  `generate_data_entries_for_type(module_id: int, data_entry_type: DataEntryTypeEnum, count: int) -> list[tuple]`
  — same row-tuple shape `generate_data_entries_for_module` already
  produces (`(data_entry_type.value, module_id, json_data, status)`), but
  every row is the given type instead of a random pick, and every row uses
  `DataEntryStatusEnum.VALIDATED` (ceiling scenario is "a unit's finished
  report", not a mix of draft/rejected rows).
- Produces (in `fixtures.py`):
  `async def build_ceiling_unit(session_factory, dsn: str, *, year: int) -> CeilingUnit`
  (`dsn` must be the same DB `session_factory` is bound to — e.g.
  `perf_pg_dsn` — never `get_settings().DB_URL`; see Step 2's docstring)
  — dataclass exposing `unit_id`, `report_id`,
  `module_id_by_type: dict[ModuleTypeEnum, int]`, and
  `sample_entry_id_by_type: dict[DataEntryTypeEnum, int]` (one entry id per
  seeded type, for routes needing a `{submodule_id}`/`{item_id}`-shaped
  param). Mutates `EXCLUDED_FROM_CEILING_FIXTURE` in `app.seed.ceilings` — no,
  it must not mutate shared state at import time; instead it _returns_ the
  measured exclusions as `CeilingUnit.excluded: dict[DataEntryTypeEnum, str]`
  and Task 3's own test asserts that set matches what's hand-written into
  `EXCLUDED_FROM_CEILING_FIXTURE` (Step 4 below), so a change in one is
  caught by the other rather than silently drifting.

- [ ] **Step 1: Add the type-scoped generator to `seed_data_entries.py`**

```python
# backend/app/seed/random_generator/seed_data_entries.py — add near
# generate_data_entries_for_module

def generate_data_entries_for_type(
    module_id: int, data_entry_type: DataEntryTypeEnum, count: int
) -> list[tuple]:
    """Like ``generate_data_entries_for_module``, but every row is the given
    type and every row is VALIDATED — the ceiling fixture (#2161) models a
    unit's finished report at worst-case scale, not a draft mix.
    """
    dto_class = DATA_ENTRY_TYPE_TO_DTO[data_entry_type]
    builder = DTO_BUILDERS[dto_class]
    rows = []
    for _ in range(count):
        payload_dict = builder()
        dto_instance = dto_class(
            data_entry_type_id=data_entry_type.value,
            carbon_report_module_id=module_id,
            **payload_dict,
        )
        rows.append(
            (
                data_entry_type.value,
                module_id,
                json.dumps(dto_instance.data, default=str),
                DataEntryStatusEnum.VALIDATED.value,
            )
        )
    return rows
```

- [ ] **Step 2: Write the fixture builder**

```python
# backend/tests/integration/performance/fixtures.py
"""Builds the #2161 ceiling-scale unit: one unit, one 2025 CarbonReport, one
module per ModuleTypeEnum, each calculator DataEntryTypeEnum seeded at its
real ceiling count (app.seed.ceilings.CEILING_PER_UNIT_YEAR), with
emissions computed through the production recalc path so factor
resolution — and therefore primary_factor_id / read-side enrichment cost —
is real, not a placeholder.
"""

from dataclasses import dataclass

import asyncpg

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES
from app.seed.ceilings import CEILING_PER_UNIT_YEAR
from app.seed.random_generator.seed_data_entries import (
    copy_insert_data_entries,
    generate_data_entries_for_type,
)
from app.seed.seed_generic_factors import seed_all_factors
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow
from tests.integration.services.data_ingestion.conftest import (
    seeded_year_with_units,
)


@dataclass(frozen=True)
class CeilingUnit:
    year: int
    unit_id: int
    report_id: int
    module_id_by_type: dict[int, int]  # ModuleTypeEnum value -> module id
    sample_entry_id_by_type: dict[DataEntryTypeEnum, int]
    excluded: dict[DataEntryTypeEnum, str]


def _owning_module_type(data_entry_type: DataEntryTypeEnum) -> int:
    for module_type_id, det_list in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
        if data_entry_type in det_list:
            return int(module_type_id)
    raise ValueError(f"{data_entry_type} has no owning module type")


async def build_ceiling_unit(session_factory, dsn: str, *, year: int) -> CeilingUnit:
    """``dsn`` must be the SAME database ``session_factory`` is bound to —
    e.g. ``perf_pg_dsn`` (the testcontainer), never ``get_settings().DB_URL``
    (the app's normal-config DB, which would silently seed the wrong
    database entirely). asyncpg wants a plain ``postgresql://`` DSN, not
    SQLAlchemy's ``+asyncpg``-suffixed one.
    """
    async with session_factory() as session:
        seeded = await seeded_year_with_units(session, year=year, n_units=1)
    unit_id = seeded.units[0].id
    report_id = seeded.reports_by_unit[unit_id].id
    module_id_by_type = {
        module_type_id: crm.id
        for (uid, module_type_id), crm in seeded.modules_by_unit_and_type.items()
        if uid == unit_id
    }

    # ``seed_all_factors`` takes an explicit session — unlike
    # ``seed_generic_factors.main()``, which opens its own ``SessionLocal()``
    # bound to the app's normally-configured DB_URL. Using ``main()`` here
    # would silently seed factors into the wrong database entirely.
    async with session_factory() as session:
        await seed_all_factors(session, year)

    asyncpg_dsn = dsn.replace("postgresql+asyncpg", "postgresql")
    conn = await asyncpg.connect(asyncpg_dsn)
    entry_ids_by_type: dict[DataEntryTypeEnum, list[int]] = {}
    try:
        # copy_insert_data_entries's temp table is ``ON COMMIT DROP`` — it
        # only survives from one CEILING_PER_UNIT_YEAR iteration to the next
        # if every iteration shares one explicit transaction (asyncpg
        # auto-commits each bare conn.execute otherwise, which would drop
        # the table right after the first CREATE). Mirrors main()'s own
        # multi-batch transaction below in this same file.
        async with conn.transaction():
            for data_entry_type, count in CEILING_PER_UNIT_YEAR.items():
                module_type_id = _owning_module_type(data_entry_type)
                module_id = module_id_by_type[module_type_id]
                rows = generate_data_entries_for_type(module_id, data_entry_type, count)
                entry_ids_by_type[data_entry_type] = await copy_insert_data_entries(
                    conn, rows
                )
    finally:
        await conn.close()

    excluded: dict[DataEntryTypeEnum, str] = {}
    sample_entry_id_by_type: dict[DataEntryTypeEnum, int] = {}
    async with session_factory() as session:
        for data_entry_type, entry_ids in entry_ids_by_type.items():
            module_id = module_id_by_type[_owning_module_type(data_entry_type)]
            result = await EmissionRecalculationWorkflow(
                session
            ).recalculate_for_data_entry_type(
                data_entry_type, year, carbon_report_module_ids=[module_id]
            )
            await session.commit()
            if result["recalculated"] == 0 or result["errors"] > 0:
                excluded[data_entry_type] = (
                    f"recalculated={result['recalculated']} "
                    f"errors={result['errors']} — seeded payload does not "
                    f"resolve a factor for {data_entry_type.name} (same class "
                    f"of gap Track C2 hit for process_emissions/plane/it)"
                )
                continue
            sample_entry_id_by_type[data_entry_type] = entry_ids[0]

    return CeilingUnit(
        year=year,
        unit_id=unit_id,
        report_id=report_id,
        module_id_by_type=module_id_by_type,
        sample_entry_id_by_type=sample_entry_id_by_type,
        excluded=excluded,
    )
```

- [ ] **Step 3: Add the session-scoped fixture to `conftest.py`**

```python
# backend/tests/integration/performance/conftest.py — append

import pytest
import pytest_asyncio

from app.seed.seed_generic_factors import INPUT_DATA_FOLDER
from tests.integration.performance.fixtures import build_ceiling_unit

CEILING_YEAR = 2025

# Real factor CSVs are gitignored dev-only data (same precondition as
# `make bootstrap-years`) — no CI checkout has them (verified: every path
# in seed_generic_factors.FACTOR_SEEDS matches .gitignore's `*.csv` under
# backend/INPUT_DATA/). Every test that depends on `ceiling_unit` (Tasks
# 3-5) is skipped via this fixture rather than failing three layers down
# in LocalFactorCSVProvider with an opaque FileNotFoundError. Task 2's
# harness spike does NOT use this fixture and always runs. See this plan's
# Global Constraints.


@pytest_asyncio.fixture(scope="session")
async def ceiling_unit(perf_session_factory, perf_pg_dsn):
    if not INPUT_DATA_FOLDER.is_dir():
        pytest.skip(f"backend/INPUT_DATA/ not present locally ({INPUT_DATA_FOLDER})")
    return await build_ceiling_unit(perf_session_factory, perf_pg_dsn, year=CEILING_YEAR)
```

- [ ] **Step 4: Write the test that measures — and pins — real exclusions**

```python
# backend/tests/integration/performance/test_ceiling_fixture_pg.py
"""Confirms every non-excluded ceiling type produced real, factor-resolved
emissions — the guard the advisor flagged: a fixture with NULL
primary_factor_id everywhere would make every later timing number measure
a cheaper-than-production code path.
"""

import pytest
from sqlmodel import col, select

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.seed.ceilings import (
    CEILING_PER_UNIT_YEAR,
    EXCLUDED_FROM_CEILING_FIXTURE,
)

pytestmark = pytest.mark.asyncio


async def test_excluded_types_match_the_hand_written_table(ceiling_unit):
    # If this fails, either a previously-working type regressed (investigate
    # before touching the table) or a previously-broken type now resolves
    # (update EXCLUDED_FROM_CEILING_FIXTURE in app/seed/ceilings.py to drop
    # it — do not just widen this assertion).
    assert set(ceiling_unit.excluded) == set(EXCLUDED_FROM_CEILING_FIXTURE)


@pytest.mark.parametrize(
    "data_entry_type", [t for t in CEILING_PER_UNIT_YEAR if t not in EXCLUDED_FROM_CEILING_FIXTURE]
)
async def test_type_has_real_factor_resolved_emissions(
    ceiling_unit, perf_session_factory, data_entry_type: DataEntryTypeEnum
):
    entry_id = ceiling_unit.sample_entry_id_by_type[data_entry_type]
    async with perf_session_factory() as session:
        rows = (
            await session.execute(
                select(DataEntryEmission).where(
                    col(DataEntryEmission.data_entry_id) == entry_id
                )
            )
        ).scalars().all()
    assert len(rows) > 0, f"{data_entry_type.name}: seeded entry has zero emissions"
    assert any(
        r.primary_factor_id is not None for r in rows
    ), f"{data_entry_type.name}: every emission row has NULL primary_factor_id"
```

- [ ] **Step 5: Run against real Docker, record whichever types fail**

Run: `cd backend && uv run pytest tests/integration/performance/test_ceiling_fixture_pg.py -v`

If any `test_type_has_real_factor_resolved_emissions` case fails, that
type's payload builder in `seed_data_entries.py` doesn't match the factor
classification codes `seed_generic_factors` seeds for it — add it to
`EXCLUDED_FROM_CEILING_FIXTURE` in `app/seed/ceilings.py` with the failure
reason (mirroring Task 3 Step 2's exclusion-message text), re-run, confirm
`test_excluded_types_match_the_hand_written_table` now passes. Do **not**
edit the builder to force a match unless you've confirmed the fix is
correct against real factor data — a forced match that doesn't reflect
production payloads reintroduces the exact confound Track F0 hit.

- [ ] **Step 6: Commit**

```bash
git add backend/app/seed/random_generator/seed_data_entries.py \
        backend/app/seed/ceilings.py \
        backend/tests/integration/performance/fixtures.py \
        backend/tests/integration/performance/test_ceiling_fixture_pg.py
git commit -m "feat(perf): seed #2161 ceiling unit via the real recalc path"
```

---

### Task 4: Systematic GET-route discovery + param binding

**Files:**

- Create: `backend/tests/integration/performance/route_registry.py`
- Test: `backend/tests/integration/performance/test_route_registry.py`

**Interfaces:**

- Produces: `discover_get_routes(app) -> list[starlette.routing.Route]`
  (every route under the `/v1` prefix whose `.methods` includes `"GET"`,
  excluding `EXCLUDED_ROUTES`). `EXCLUDED_ROUTES: dict[str, str]` keyed by
  the route's raw `.path` (e.g. `"/v1/auth/login"`), valued by a one-line
  reason. `bind_path(path: str, ceiling_unit: CeilingUnit) -> str | None`
  — returns the path with every `{param}` filled from `ceiling_unit` /
  `PARAM_OVERRIDES`, or `None` (with the missing param name) if a param
  can't be resolved — a route with an unresolvable param **fails
  collection**, it is not silently skipped.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/performance/test_route_registry.py
"""Every GET route under /v1 must be either bindable from the ceiling
fixture or explicitly excluded with a reason — a new route added later
fails this test until someone does one of the two, which is the point.
"""

from app.main import app
from tests.integration.performance.route_registry import (
    EXCLUDED_ROUTES,
    bind_path,
    discover_get_routes,
)


def test_every_discovered_route_is_excluded_or_documented_bindable():
    routes = discover_get_routes(app)
    assert len(routes) > 40  # sanity floor — catches discover_get_routes breaking silently

    unresolvable = []
    for route in routes:
        # Static param names only, no fixture required — proves the path
        # template is well-formed and every {param} has a known source.
        result = bind_path(route.path, ceiling_unit=None, dry_run=True)
        if result is None:
            unresolvable.append(route.path)

    assert not unresolvable, (
        f"routes with no known param binding and no exclusion entry: "
        f"{unresolvable} — add a PARAM_OVERRIDES entry, extend "
        f"CeilingUnit, or add to EXCLUDED_ROUTES with a reason"
    )


def test_excluded_routes_all_carry_a_reason():
    assert all(isinstance(reason, str) and reason for reason in EXCLUDED_ROUTES.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/performance/test_route_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'tests.integration.performance.route_registry'`

- [ ] **Step 3: Write the implementation**

```python
# backend/tests/integration/performance/route_registry.py
"""Discovers every GET route under /v1 from the live FastAPI app (not a
hand-written list, per #2161's "systematically test ... all GET" ask), and
binds each route's path params from the ceiling fixture.

A route this module can neither bind nor find in EXCLUDED_ROUTES fails
test_route_registry.py's collection-time check — that failure IS the
systematic property: nobody can add a new GET endpoint and have it silently
skip this suite.
"""

import re

from starlette.routing import Route

# path -> one-line reason. Every entry here is a route this suite
# deliberately does not time, not a route nobody got around to.
EXCLUDED_ROUTES: dict[str, str] = {
    # OAuth redirect/callback flows — not data-driven, covered by
    # tests/integration/v1/test_auth*.py.
    "/v1/auth/login": "OAuth redirect, not data-driven",
    "/v1/auth/callback": "OAuth redirect, not data-driven",
    # Binary downloads from object storage — latency is storage-backend
    # bound, not data_entries-count bound.
    "/v1/files/": "binary download, storage-bound not DB-bound",
    "/v1/files/{file_path:path}": "binary download, storage-bound not DB-bound",
    # Third-party network calls — latency is the external service's, not ours.
    "/v1/connectors": "hits external connector systems, not this DB",
    "/v1/connectors/{connector}/connection": "hits external connector systems, not this DB",
    # SSE/streaming — no single "response received" latency to assert on.
    "/v1/sync/jobs/{job_id}/stream": "SSE stream, no bounded response time",
    "/v1/sync/pipelines/{pipeline_id}/stream": "SSE stream, no bounded response time",
    # Large streamed CSV export — different performance contract (throughput,
    # not latency-to-first-byte).
    "/v1/backoffice/export": "streamed export, throughput contract not latency",
    # See this plan's "Explicitly out of scope" section — planner ceilings
    # need a different fixture shape (SimulatorPlan + multi-year reports).
    "/v1/project-plans/{plan_id}/years/{year}": "planner ceiling fixture out of scope, see #2161 plan follow-up",
    "/v1/project-plans/{plan_id}": "planner ceiling fixture out of scope, see #2161 plan follow-up",
    "/v1/project-plans/{plan_id}/years": "planner ceiling fixture out of scope, see #2161 plan follow-up",
    "/v1/project-plans/{plan_id}/prefill/{job_id}": "planner ceiling fixture out of scope, see #2161 plan follow-up",
    # Per-audit-log-row lookup — this fixture creates no AuditLog rows.
    "/v1/audit/activity/{log_id}": "no seeded AuditLog rows in this fixture",
}

_PARAM_RE = re.compile(r"\{([^:}]+)(?::[^}]+)?\}")


def discover_get_routes(app) -> list[Route]:
    routes = []
    for route in app.routes:
        if not isinstance(route, Route):
            continue
        if not route.path.startswith("/v1"):
            continue
        if "GET" not in (route.methods or set()):
            continue
        if route.path in EXCLUDED_ROUTES:
            continue
        routes.append(route)
    return routes


def bind_path(path: str, ceiling_unit, *, dry_run: bool = False) -> str | None:
    """Fill every ``{param}`` in ``path``.

    ``dry_run=True`` (used by the collection-time sanity test) only checks
    that every param NAME is one this function knows how to resolve, without
    requiring a real ``ceiling_unit`` — keeps that test fixture-free and fast.
    """
    param_names = _PARAM_RE.findall(path)
    if not param_names:
        return path

    known = {"unit_id", "year", "carbon_report_id", "module_id", "submodule_id"}
    if dry_run:
        return path if all(p in known for p in param_names) else None

    values = {
        "unit_id": ceiling_unit.unit_id,
        "year": ceiling_unit.year,
        "carbon_report_id": ceiling_unit.report_id,
        # Worst-case single module: the largest-ceiling group (purchase-family
        # types share one module_type — see MODULE_TYPE_TO_DATA_ENTRY_TYPES).
        "module_id": max(ceiling_unit.module_id_by_type.values()),
        "submodule_id": next(iter(ceiling_unit.sample_entry_id_by_type.values())),
    }
    try:
        return re.sub(_PARAM_RE, lambda m: str(values[m.group(1)]), path)
    except KeyError as exc:
        raise ValueError(f"bind_path: no known value for {exc} in {path!r}") from exc
```

- [ ] **Step 4: Run test, fix any newly-discovered unresolvable route**

Run: `cd backend && uv run pytest tests/integration/performance/test_route_registry.py -v`

If it fails listing routes like `/v1/factors/{data_entry_type}/class-subclass-map`
or `/v1/taxonomies/module/{module}`, add a `PARAM_OVERRIDES`-style constant
(a `dict[str, dict[str, str]]` from path -> `{param_name: literal_value}`,
e.g. `{"data_entry_type": "member"}`) checked before the generic `known`
set in `bind_path`, or add the route to `EXCLUDED_ROUTES` with a genuine
reason — do not delete the assertion to make it pass.

Expected once resolved: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/performance/route_registry.py \
        backend/tests/integration/performance/test_route_registry.py
git commit -m "feat(perf): discover /v1 GET routes systematically, bind params from fixture"
```

---

### Task 5: The ceiling-scale latency suite

**Files:**

- Create: `backend/tests/integration/performance/test_get_endpoints_ceiling_pg.py`

**Interfaces:**

- Consumes: `ceiling_unit` (Task 3), `perf_app` (Task 2),
  `discover_get_routes`/`bind_path` (Task 4).

- [ ] **Step 1: Write the test**

```python
# backend/tests/integration/performance/test_get_endpoints_ceiling_pg.py
"""#2161: every GET route under app/api/v1, timed against a unit seeded at
real ceiling scale (app.seed.ceilings). Budget is 200ms — a worst-case-data
budget, distinct from the guardrails' 80ms/400ms normal-load budget (see
this plan's Global Constraints).
"""

import time

import httpx
import pytest

from app.main import app
from tests.integration.performance.route_registry import bind_path, discover_get_routes

pytestmark = pytest.mark.asyncio

CEILING_BUDGET_MS = 200


def _route_ids():
    return [r.path for r in discover_get_routes(app)]


@pytest.mark.parametrize("route", discover_get_routes(app), ids=_route_ids())
async def test_get_endpoint_within_ceiling_budget(perf_app, ceiling_unit, route):
    bound_path = bind_path(route.path, ceiling_unit)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=perf_app), base_url="http://test"
    ) as client:
        start = time.perf_counter()
        resp = await client.get(bound_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

    assert resp.status_code < 500, (
        f"{route.path} -> {bound_path}: {resp.status_code} {resp.text[:300]}"
    )
    assert elapsed_ms < CEILING_BUDGET_MS, (
        f"{route.path} -> {bound_path}: {elapsed_ms:.1f}ms exceeds "
        f"{CEILING_BUDGET_MS}ms ceiling-scale budget"
    )
```

- [ ] **Step 2: Run against real Docker**

Run: `cd backend && uv run pytest tests/integration/performance/test_get_endpoints_ceiling_pg.py -v`

Expected on first run: some endpoints will genuinely exceed 200ms — that's
real signal, not a harness bug. For each failure, read the failing route's
handler before touching the budget: if 2050's Tracks C/D/E's N+1 pattern is
present (per-entry queries scaling with the seeded ceiling count), file a
follow-up issue referencing 2050 rather than loosening `CEILING_BUDGET_MS`.
Loosening the budget to make a real N+1 pass defeats the point of this
suite.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/performance/test_get_endpoints_ceiling_pg.py
git commit -m "test(perf): time every /v1 GET route against #2161 ceiling data"
```

---

### Task 6: Document the local-only nature — this suite does not run in CI

**Files:**

- Modify: `backend/tests/integration/performance/__init__.py` (docstring)
- Modify: `docs/src/contributing/guardrails.md` is NOT touched — this is a
  suite-specific constraint, not a new project-wide rule.

`tests/integration` is picked up wholesale by
`test-cov-xml-integration`/`integration-tests.yml`, same as every other
Docker-gated PG suite — so nothing needs wiring for _discovery_. What Task
2/3 established is the opposite problem: this suite **cannot succeed** in
that workflow's fresh checkout, because `backend/INPUT_DATA/*.csv` (real
factor data) is gitignored and CI never provisions it. Tasks 3-5's tests
skip cleanly via the `ceiling_unit` fixture rather than failing the daily
run — confirm that's actually what happens, not just asserted in the docstring.

- [ ] **Step 1: Confirm the daily workflow skips cleanly instead of failing**

Run (on a machine/CI checkout with no `backend/INPUT_DATA/`):
`cd backend && uv run pytest tests/integration/performance/ -v`

Expected: `test_harness_spike_pg.py` and `test_route_registry.py` PASS
(neither needs `ceiling_unit`); every test in `test_ceiling_fixture_pg.py`
and `test_get_endpoints_ceiling_pg.py` reports SKIPPED with the
`backend/INPUT_DATA/ not present locally` reason, not ERROR.

- [ ] **Step 2: Add the suite docstring**

```python
# backend/tests/integration/performance/__init__.py
"""#2161 ceiling-scale performance suite.

See docs/src/implementation-plans/2161-ceiling-scale-perf-fixtures.md for
the design: a single Postgres-backed unit seeded at #2161's real
per-data_entry_type ceilings, emissions computed via the production recalc
path, every /v1 GET route timed against it.

Requires Docker (all tests) AND backend/INPUT_DATA/*.csv locally (real
factor data, gitignored, same precondition as `make bootstrap-years`) for
Tasks 3-5's tests — those skip cleanly without it. This means, unlike the
other suites under tests/integration/, this one does NOT run to completion
in the daily integration-tests.yml workflow's fresh checkout: run it
locally on demand.
"""
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/performance/__init__.py
git commit -m "docs(perf): document the ceiling suite's local-only INPUT_DATA constraint"
```

## Self-review notes (from the plan author, not a task)

- Spec coverage: ceiling table (Task 1) ✓, real-factor seeding (Task 3) ✓,
  systematic GET discovery (Task 4) ✓, timing assertion (Task 5) ✓, harness
  proof before scaling up (Task 2) ✓.
- Planner ceilings (`planner_headcount`/`purchase`/`purchase_budget`) and
  `simulator_plan.py` GETs are explicitly out of scope — see that section
  up top — not silently dropped.
- `EXCLUDED_FROM_CEILING_FIXTURE` in `app/seed/ceilings.py` starts empty by
  design; Task 3 Step 5 is where it gets populated for real, from measured
  failures, not guessed in advance.
