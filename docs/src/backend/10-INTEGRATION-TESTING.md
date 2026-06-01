# Backend Integration Testing

This document describes the backend integration test strategy: where
tests live, what they cover, how to run them, what fixtures they share,
and where to look when CI fails. It is the orientation guide for anyone
landing in `backend/tests/integration/` for the first time.

For broader backend context see:

- [Architecture](02-ARCHITECTURE.md) - Layer patterns
- [File Structure](03-FILE_STRUCTURE.md) - Code organization
- [Permission System](06-PERMISSION-SYSTEM.md) - Authorization model

## Overview

Integration tests exercise the backend against real infrastructure.
Most of them spin up a Postgres testcontainer and drive the same code
paths the FastAPI runtime executes. They cover behaviour that unit
tests cannot: partial unique indexes under concurrency, JSONB round
trips, `ON CONFLICT` upserts, transactional semantics across pooled
connections, and chain-job orchestration end-to-end.

Two CI gates run them on different cadences:

| Suite                | Workflow                | Cadence         | Coverage gate |
| -------------------- | ----------------------- | --------------- | ------------- |
| `tests/unit/`        | `test.yml`              | every PR + push | 60%           |
| `tests/integration/` | `integration-tests.yml` | daily 03:30 UTC | 45%           |

Splitting the suites is a deliberate cost trade-off. A PR that touches
`tests/integration/services/data_ingestion/` will not see those
failures until the next daily run. Plan accordingly: when you change
the bulk-ingest pipeline, consider dispatching the daily workflow
manually (`gh workflow run integration-tests.yml`) before merge.

## Test Layout

```
backend/tests/
├── unit/                                # Mocked I/O, fast, every PR
│   ├── core/   models/   providers/
│   ├── repositories/   schemas/
│   ├── services/   tasks/   workflows/
│   └── v1/                              # API-layer unit tests
│
├── integration/                         # Real infrastructure, daily CI
│   ├── data_ingestion/                  # CSV upload smoke (2 files)
│   ├── es_integration/                  # Elasticsearch container
│   ├── modules/   providers/            # Provider/module wiring
│   ├── v1/                              # End-to-end auth + permission
│   └── services/data_ingestion/         # The hot zone (28+ PG-backed files)
│
├── fixtures/csv/                        # Trimmed, committed CSVs (CI-safe)
└── conftest.py                          # Root model factories
```

The `services/data_ingestion/` directory is the heart of the
integration suite. It pins the bulk-ingest -> recalc -> aggregation
pipeline that owns `data_entry_emissions` and
`carbon_reports.stats` writes. Touching anything in
`app/api/v1/data_sync.py`, `app/services/data_ingestion/`,
`app/tasks/`, or the recalc workflows means the tests there are your
safety net.

The other integration directories are smaller in scope:

- `data_ingestion/` (top-level) - CSV upload smoke + validation
  contracts at the HTTP boundary.
- `es_integration/` - Elasticsearch client round trips against a real
  ES container.
- `v1/` - Auth and permission paths exercised through the full FastAPI
  stack (no mocks of `is_permitted`).
- `modules/` and `providers/` - Module registry and provider wiring
  smoke tests.

## The Postgres Testcontainer

`backend/tests/integration/services/data_ingestion/conftest.py`
provisions Postgres for the suite. Three layers:

1. `postgres_container` - session-scoped fixture that starts
   `postgres:16-alpine` on port `55432`. Pulls the image if needed and
   waits for the "ready" log marker to appear twice (Postgres logs it
   once during init and once after the final restart).
2. `pg_dsn` - function-scoped DSN. Drops and re-creates every SQLModel
   table before yielding so each test starts on a clean schema.
3. `pg_dsn_with_310b` - `pg_dsn` plus the partial unique indexes that
   the Plan 310B migration adds (`uq_factor_identity` and
   `uq_factor_identity_no_year`).

Schema construction uses `SQLModel.metadata.create_all`, **not**
Alembic. Any DDL added in a migration that isn't expressed on a
`SQLModel` class -- partial unique indexes, custom enum values,
expression indexes -- must be replayed in a conftest helper or those
tests will fail when production code hits an `ON CONFLICT` clause that
has no index to bind to.

The canonical example is `_install_plan_310b_indexes` in the same
conftest. When you add a new migration with bare DDL, mirror it there
or write a local fixture in your test file (see
`test_aggregation_dedup_index_pg.py` for that pattern).

```python
async def _install_plan_310b_indexes(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity "
            "ON factors (data_entry_type_id, year, emission_type_id, "
            "(classification::text)) WHERE year IS NOT NULL"
        ))
        # ... and the year-NULL variant
```

## Foundation Helpers

Plan 310 Unit 1 added four shared helpers to the same conftest so the
fan-out tests don't each re-invent fixture composition or chain-driving
plumbing.

### `seeded_year_with_units`

```python
seeded = await seeded_year_with_units(session, year=2025, n_units=2)
```

Lays down a `YearConfiguration`, `n_units` `Unit` rows (each with its
own `CarbonProject`), one `CarbonReport` per unit, and one
`CarbonReportModule` per `(unit, ModuleTypeEnum)` pair. Returns a
frozen `SeededYear` exposing `units`, `reports_by_unit`, and
`modules_by_unit_and_type` for O(1) lookup.

The helper commits before returning so subsequent reads from a
different session see the rows.

### `assert_stats_match`

```python
await assert_stats_match(
    session,
    module_id=crm.id,
    expected={"total_co2eq": 1234.5},
)
```

Reads `carbon_report_modules.stats` and recursively asserts every
key/value in `expected` is present in the persisted JSON (extra keys
are fine -- it's a subset match). On mismatch, raises
`AssertionError` with a precise dotted path:
`stats[module_id=42].by_emission_type.5: missing`.

Pass `expected={}` to assert that `stats` is at least a dict.

### `csv_fixture_path`

```python
path = csv_fixture_path("headcount", "data")
```

Resolves `(module, kind)` to an absolute CSV path. Resolution order:

1. `backend/tests/fixtures/csv/<trimmed-name>.csv` - the committed,
   CI-safe trimmed fixture if one exists.
2. `backend/seed_data/<flat-basename>.csv` - the local-only,
   gitignored full seed file used in development.

CI cannot reach `seed_data/`. If you write a test that needs a CSV,
ship a trimmed committed fixture under `backend/tests/fixtures/csv/`
and register it in `_TRIMMED_CSV_FIXTURES`.

### `dispatch_csv_and_wait`

```python
parent, children = await dispatch_csv_and_wait(
    session_factory=factory,
    file_path=csv_fixture_path("headcount", "data"),
    target_type=TargetType.DATA_ENTRIES,
    module_type_id=int(ModuleTypeEnum.HEADCOUNT),
    data_entry_type_id=int(DataEntryTypeEnum.HEADCOUNT_MEMBER),
    year=2025,
    provider_class=HeadcountCsvProvider,
)
```

Drives a CSV ingest end-to-end against the test PG session factory.
Mirrors the production `app.tasks.runner.run_job` shape: load the row,
invoke its handler, **commit the data session** on success, roll back
on exception, then mark the job `FINISHED` with the result.

Returns `(parent_job, [children])` where `children` are every job
sharing the parent's `pipeline_id`.

The handler's data-session commit is load-bearing. Handlers like
`aggregation` only `flush()` and rely on the runner to commit; without
the commit, every chained handler silently drops its domain writes
and `assert_stats_match` reads pre-handler state.

## Why Tests Don't POST to `/sync/dispatch`

The FastAPI runner (`app.tasks.runner.run_job`) opens its own sessions
via `app.db.SessionLocal`. The test PG container is bound to a
different DSN, so anything the runner writes lands in a database the
test never inspects.

Patching `SessionLocal` per call site is fragile across many test
files. `dispatch_csv_and_wait` centralises the proven pattern:

1. Create the parent `csv_ingest` row directly.
2. Patch `chain_mod.fire_and_forget` so child IDs queue on the test
   side instead of fanning out to the runner.
3. Drain the queue breadth-first using the test's session factory.

`test_full_dag_pipeline_pg.py` is the original implementation; the
helper extracted it for reuse.

## Two-Layer Permission Scope Model

Every `/sync/*` endpoint enforces two permission layers. Tests that
exercise authorization need to mock both -- forgetting one is the most
common cause of a "tests pass locally, fail on a permission edge"
regression.

### Layer 1 - Global

Every endpoint requires `backoffice.data_management.{view,edit,sync}`
on the calling user. This is checked via `is_permitted` at the
service-layer entry point and is module-agnostic.

### Layer 2 - Per-Job (Conditional)

`_check_job_scope` in `backend/app/api/v1/data_sync.py:132` runs
`check_module_permission` **only** when
`_institutional_id_for_job` returns a non-`None` value.
`EntityType` (defined in `backend/app/models/data_ingestion.py:20`)
has exactly three members:

| Entity type            | `_institutional_id_for_job`              | Layer 2 fires? |
| ---------------------- | ---------------------------------------- | -------------- |
| `MODULE_UNIT_SPECIFIC` | unit's institutional_id (resolved)       | yes            |
| `MODULE_PER_YEAR`      | `None` (cross-unit aggregation / recalc) | no -- L1 only  |
| `GLOBAL_PER_YEAR`      | `None` (no module — unit sync, etc.)     | no -- L1 only  |

This matters: aggregation and emission_recalc jobs are
`MODULE_PER_YEAR` and gated by Layer 1 alone. Per-unit ingestion jobs
(direct CSV uploads on a specific module-and-unit) are
`MODULE_UNIT_SPECIFIC` and hit both layers. `GLOBAL_PER_YEAR` jobs
(unit sync) carry no module at all and short-circuit even earlier at
the `module_type_id is None` guard inside `_check_job_scope`, before
the institutional_id resolution runs.

### Test Patterns

Most tests use a `pg_app` fixture that mocks both layers to focus on
response-shape assertions. Cross-tenant deny tests deliberately bypass
`pg_app` and wire the deny at one specific layer:

- **Layer 1 deny** - inject `is_permitted=_deny` and assert 403
  before any DB read. See `test_active_pipelines_endpoint_pg.py`.
- **Layer 2 deny** - mock `_institutional_id_for_job` to return a
  unit ID, then mock `check_module_permission` to raise. See
  `test_sync_pipeline_stream_endpoint_pg.py::test_cross_tenant_pipeline_returns_403`.

When you add a new permission check (a new positional argument to
`get_module_permission_decision`, a new endpoint requiring a different
scope), every fixture that mocks the prior shape must be updated.

## Strategy A vs Strategy B Rematch

The `EmissionRecalculationWorkflow` has two code paths for finding the
right factor at recompute time. Both are pinned by integration tests.

### Strategy A - JSON-link path

`DataEntries` carry their factor reference inside `entry.data` (the
JSON column). When a factor upsert runs, `EmissionRecalculationWorkflow`
walks `factor_lookup` and rewrites `entry.data['primary_factor_id']`
for handlers whose `kind_field` (and optional `subkind_field`) live on
`entry.data`.

Modules covered:

- `equipment.electric_consumption` (it / scientific / other)
- `purchase` (purchase_common / purchase_additional)
- `external_cloud_and_ai` (external_cloud / external_ai)
- `process_emissions`
- `research_facilities` (common / animals)
- `buildings.energy_combustion`

Test: `test_strategy_a_rematch_pg.py`.

### Strategy B - FK-link path

`DataEntries` have no `primary_factor_id` on `entry.data`; the only
factor link is `data_entry_emissions.primary_factor_id`. These
handlers never enter the JSON-link rematch branch -- they re-derive
the factor via classification on every recompute through
`upsert_by_data_entry`.

Modules covered:

- `headcount.member` and `headcount.student`
- `professional_travel.plane` and `professional_travel.train`
- `buildings.building_embodied_energy`

Test: `test_strategy_b_rematch_pg.py`.

## Source-Type Uniformity

`EmissionRecalculationWorkflow` recomputes **all** values of
`DataEntrySourceEnum` uniformly -- there is no source filter. This is
a load-bearing property: a regression that filtered to a single source
would silently leave non-CSV entries stale.

Plan 310 Unit 6 pins this contract in
`test_recalc_source_uniformity_pg.py`. When you add a new
`DataEntrySourceEnum` member, that test must keep passing without
modification.

## Concurrency and Dedup

Three partial unique indexes guard the bulk-ingest pipeline against
concurrent writers (multiple pods, retried tasks, racing user actions):

| Index                                      | Scope                                                                           | Used by                       |
| ------------------------------------------ | ------------------------------------------------------------------------------- | ----------------------------- |
| `ix_data_ingestion_jobs_is_current_unique` | `(combo, is_current=TRUE)`                                                      | `claim_job`                   |
| `uq_aggregation_active`                    | `(module_type_id, year)` where `job_type='aggregation'`                         | `chain_job(dedup_config=...)` |
| `uq_emission_recalc_active`                | `(module_type_id, data_entry_type_id, year)` where `job_type='emission_recalc'` | `chain_job(dedup_config=...)` |

`claim_job` (`backend/app/repositories/data_ingestion.py:473`) uses
the first index for atomic claims: only one pod can hold the
`is_current=TRUE` row for a combo at a time. `chain_job` uses the
other two to collapse N concurrent fan-out attempts into a single
pending row.

Tests:

- `test_pod_safety_310a_pg.py` - `claim_job` race semantics across
  separate engines (= separate connections = separate transactions).
- `test_aggregation_dedup_chain_pg.py` and
  `test_aggregation_dedup_index_pg.py` - aggregation collapse.
- `test_emission_recalc_dedup_pg.py` - emission-recalc collapse.

SQLite cannot represent partial unique indexes the same way Postgres
does, so these tests are PG-only.

## SSE Endpoints

Two server-sent-events endpoints stream pipeline status to the
frontend's `pipelineStateStore`:

- `GET /sync/jobs/{id}/stream` - one job's lifecycle.
- `GET /sync/pipelines/{id}/stream` - every job in a pipeline.

Tests live in `test_sync_pipeline_stream_endpoint_pg.py`. Coverage of
the streaming **body** is partial: `httpx.ASGITransport` has flaky
cancellation semantics through SSE generators, so most tests pin the
contract assertions (404 short-circuit before the stream opens, 403
permission gate, header negotiation).

The `_FakeRequest` pattern in `test_disconnect_releases_pool_slot` is
the workaround for the cases where you must verify the streaming side:
substitute a fake request whose `is_disconnected()` you control
directly, sidestepping the transport.

## kg_co2eq Override

`DataEntry.data` reserves the key `__kg_co2eq_override__` for
ingestion-time overrides. The bulk-path providers
(`base_csv_provider`, the Tableau travel provider) write
`OUT_CO2_CORRECTED` (or the parsed CSV value) into this key under
`BULK_PATH_PURE_ASYNC=True`.

The runner-driven recalc workflow then reads `data_entries` and calls
`DataEntryEmissionService.upsert_by_data_entry`, which has no
`kg_co2eq_override` parameter -- the carrier in `entry.data` is the
only path the value travels.

Test: `test_kg_co2eq_override_async_path_pg.py` (post PR #1079
V2 fix).

## Running Tests

All commands assume the `rtk` prefix; the harness uses Rust Token
Killer for compact output.

```bash
cd backend

# Fast unit run (PR CI gate)
rtk uv run pytest tests/unit/ -v

# PG-backed integration suite (Docker required, daily CI gate)
rtk uv run pytest tests/integration/services/data_ingestion/ -v

# Single test file
rtk uv run pytest tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py -v

# Single test
rtk uv run pytest \
  tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py::test_full_pipeline_chains_recalc_then_aggregation -v
```

The Makefile mirrors what CI runs:

```bash
make test                       # tests/unit, --cov-fail-under=60
make test-cov-xml               # PR CI target (unit + xml)
make test-cov-xml-integration   # daily CI target (integration + xml)
```

The integration suite needs a running Docker daemon. The session
fixture pulls `postgres:16-alpine` and binds it to `localhost:55432`;
that port must be free.

## Conventions

- **rtk prefix**. Wrap every command with `rtk` -- including inside
  command chains: `rtk git add . && rtk git commit -m "..."`.
- **Force-add CSV fixtures**. The repo's root `.gitignore` matches
  `*.csv`. New trimmed fixtures need `git add -f
backend/tests/fixtures/csv/<file>.csv`.
- **Trimmed fixtures live under `backend/tests/fixtures/csv/`**.
  `seed_data/<module>/*.csv` is gitignored and dev-only; CI cannot
  reach it.
- **Commit `data_session`, don't just flush**. The runner pattern
  commits on success, rolls back on exception. Tests that drive
  handlers directly must follow the same shape -- see
  `dispatch_csv_and_wait._run_one_job` for the canonical
  implementation.
- **Use `pg_dsn_with_310b` when your code path hits an `ON CONFLICT`
  upsert against `factors`**. The bare `pg_dsn` doesn't have the
  partial unique indexes the upsert binds to.

## When CI Breaks

### "I broke unit tests"

The PR CI gate failed. Reproduce locally:

```bash
cd backend
rtk uv run pytest tests/unit/ -v
```

Most failures are isolated to the file you touched. If a shared
fixture changed, look at `backend/tests/conftest.py`.

### "Daily integration CI is red"

Two common causes:

1. **A migration didn't replay in `pg_dsn_with_310b`**. New partial
   unique indexes or enum values added to a migration must mirror in
   conftest, or `ON CONFLICT` upserts and enum casts will fail at
   runtime. Mirror the DDL in `_install_plan_310b_indexes` (or a
   sibling helper if the index is unrelated to Plan 310B).

2. **A fixture's mock doesn't cover a newly-added permission layer**.
   PR #1079 added a per-module filter on `/active-pipelines`; the
   fixture only mocked `is_permitted` (Layer 1) and not the new
   `get_module_permission_decision` call, so
   `test_active_pipelines_endpoint_pg.py` failed in daily CI a day
   after the PR landed. When you add a permission check, audit every
   `pg_app`-style fixture for the same shape.

Reproduce locally:

```bash
cd backend
rtk uv run pytest tests/integration/services/data_ingestion/ -v
```

Docker must be running. The first run pulls
`postgres:16-alpine`; subsequent runs reuse the cached image.

### "Test hangs forever"

Usually an SSE generator awaiting an event that never fires. The
canonical example: a `test_cross_tenant_pipeline_returns_403`
regression hung for six hours in May 2026. Root cause was a scope-check
short-circuit combined with an SSE poll loop with no exit condition;
the fix was a monkeypatch on the poll plus an `httpx` timeout cap.

If a test hangs, look for:

- An `async for event in stream` that has no termination event
  injected.
- An `httpx.AsyncClient` without a `timeout=` set.
- A `_FakeRequest` whose `is_disconnected()` returns `False`
  unconditionally.

Add a `timeout=` to the client and a sentinel event to the stream
mock; the generator will then raise instead of blocking.

## See Also

- [Architecture](02-ARCHITECTURE.md) - Layer patterns
- [File Structure](03-FILE_STRUCTURE.md) - Code organization
- [Permission System](06-PERMISSION-SYSTEM.md) - Authorization model
- [File Upload Flow](08-FILE-UPLOAD-FLOW.md) - HTTP-side ingest
  contract
- Backend implementation plans: `docs/src/implementation-plans/310-*.md`
- Code review notes: `docs/code-review/310-overall-review.md`

## Summary

Backend integration tests run on a daily CI cadence and exercise real
Postgres behaviour the unit suite cannot reach. The hot zone is
`backend/tests/integration/services/data_ingestion/` -- 22 PG-backed
files covering the bulk-ingest pipeline.

Schema is built via `SQLModel.metadata.create_all`, so any
migration-only DDL must be replayed in conftest. Helpers in the same
conftest (`seeded_year_with_units`, `assert_stats_match`,
`csv_fixture_path`, `dispatch_csv_and_wait`) compose the fan-out tests
without each one re-inventing fixtures.

Two permission layers gate every `/sync/*` endpoint: a global scope
checked on every request, and a per-job module check that fires only
when the job has a non-`None` institutional ID. Forgetting either is
the most common cause of a flaky permission regression.

When daily CI fails, the usual suspects are a missing index replay or
a fixture that hasn't picked up a new permission call.
