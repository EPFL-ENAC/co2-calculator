"""Postgres testcontainer fixtures for data_ingestion integration tests.

Spins up a real Postgres container so we can exercise behavior in-memory
SQLite cannot — partial unique indexes tripping under concurrency, true
transactional semantics, JSONB ordering, etc.

Patterned on ``tests/integration/es_integration/conftest.py``.

Foundation helpers (Plan 310 test-coverage batch, Unit 1/11)
============================================================

The bottom half of this file exposes the four helpers that Units 2-11
of the test-coverage batch share, so the fan-out workers don't each
re-invent fixture composition or chain-driving plumbing:

* ``seeded_year_with_units`` — factory that lays down a ``YearConfiguration``,
  ``n_units`` ``Unit``s, one ``CarbonReport`` per unit, and one
  ``CarbonReportModule`` per ``(unit, ModuleTypeEnum)`` pair.  Returns
  a frozen ``SeededYear`` dataclass exposing dictionaries keyed by
  ``unit_id`` and ``(unit_id, module_type_id)`` for O(1) lookup.

* ``assert_stats_match`` — reads ``carbon_report_modules.stats`` for a
  given ``module_id`` and recursively asserts every key/value in
  ``expected`` is present in the persisted JSON (extra keys allowed).
  Surfaces a precise diff path on failure.

* ``csv_fixture_path`` — resolver that maps ``(module, kind)`` to the
  on-disk CSV.  Prefers the trimmed, committed fixtures under
  ``backend/tests/fixtures/csv/`` (CI-safe), falls back to the local
  ``backend/seed_data/<flat>.csv`` (gitignored, dev-only).  The
  ``seed_data`` layout is FLAT (e.g. ``seed_data/headcount_data.csv``,
  not ``seed_data/headcount/headcount_data.csv``) — the spec said
  nested but the repo uses flat.  Raises ``FileNotFoundError`` with a
  clear message when no canonical seed exists for a pair.

* ``dispatch_csv_and_wait`` — drives a CSV ingest end-to-end against
  the test PG session factory.  Mirrors the proven pattern from
  ``test_full_dag_pipeline_pg.py``: patch ``chain_mod.fire_and_forget``
  to queue child ids on the test side and run them via the test's PG
  session factory rather than the runner's production ``SessionLocal``.
  Returns ``(parent_job, [child_jobs])`` for assertion.

  Why not a real HTTP POST to ``/v1/sync/dispatch``?  ``app.tasks.runner.
  run_job`` opens its own sessions via ``app.db.SessionLocal``; the test
  PG would never see what the runner writes.  Rather than patch
  ``SessionLocal`` per call site (fragile across 11 worker units), the
  helper accepts a ``session_factory`` and a ``dispatcher`` callable
  that creates the parent job — Units 2-11 compose freely on top.
"""

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Optional
from unittest.mock import MagicMock, patch
from uuid import uuid4

import docker
import docker.errors
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# Ensure every model class is registered with SQLModel.metadata before
# create_all runs.  Top-level tests/conftest.py imports many of these for
# the SQLite suite; we re-import here to be self-contained.
from app.models import data_ingestion  # noqa: F401
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import (
    CarbonReport,
    CarbonReportModule,
    CarbonReportType,
)
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ALL_MODULE_TYPE_IDS
from app.models.unit import Unit
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration

PG_IMAGE = "postgres:16-alpine"
PG_CONTAINER_NAME = "test-data-ingestion-postgres"
PG_PORT = 55432
PG_DB = "test_data_ingestion"
PG_USER = "test"
PG_PASSWORD = "test"
PG_READY_MARKER = b"database system is ready to accept connections"


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.fixture(scope="session")
def postgres_container(docker_client):
    """Spin up a Postgres container for the test session."""
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
            print(f"Pulling Postgres image: {PG_IMAGE}")
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

        # Postgres logs the ready marker twice: once during init, once after
        # the final restart.  Wait for the second occurrence.
        timeout = 60
        deadline = time.time() + timeout
        while time.time() < deadline:
            container.reload()
            if container.status == "running":
                if container.logs().count(PG_READY_MARKER) >= 2:
                    print("Postgres container is ready!")
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"Postgres container failed to become ready within {timeout}s"
            )

        url = (
            f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}"
        )
        yield {"url": url, "container": container}

    finally:
        try:
            c = docker_client.containers.get(PG_CONTAINER_NAME)
            c.stop(timeout=10)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            print(f"Error stopping postgres container: {e}")


@pytest_asyncio.fixture(scope="function")
async def pg_dsn(postgres_container):
    """Function-scoped DSN against a freshly-created schema.

    Drops and re-creates all SQLModel tables before yielding so each test
    starts from a clean slate.  Tests that need their own engines (e.g.
    concurrency tests with one engine per simulated pod) use this DSN.
    """
    url = postgres_container["url"]
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    await engine.dispose()
    yield url


@pytest_asyncio.fixture(scope="function")
async def pg_session(pg_dsn):
    """Function-scoped AsyncSession against the fresh schema."""
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _install_plan_310b_indexes(engine) -> None:
    """Create the partial unique indexes that Plan 310B's migration adds.

    ``pg_dsn`` builds tables via ``SQLModel.metadata.create_all``, which
    doesn't know about the migration's bare DDL.  Mirror it here so
    ``ON CONFLICT`` inference can find the index it needs to bind to.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity "
                "ON factors (data_entry_type_id, year, emission_type_id, "
                "(classification::text)) "
                "WHERE year IS NOT NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity_no_year "
                "ON factors (data_entry_type_id, emission_type_id, "
                "(classification::text)) "
                "WHERE year IS NULL"
            )
        )


@pytest_asyncio.fixture(scope="function")
async def pg_dsn_with_310b(pg_dsn):
    """``pg_dsn`` plus Plan 310B's migration-only partial unique indexes.

    ``pg_dsn`` builds tables via ``SQLModel.metadata.create_all``, which
    doesn't run Alembic and therefore never creates the
    ``uq_factor_identity`` / ``uq_factor_identity_no_year`` partial unique
    indexes that ``factor_repo.upsert_factors`` needs to bind its
    ``ON CONFLICT`` clause.  Tests that exercise the upsert path (or any
    code reachable from it) should depend on this fixture instead of the
    bare ``pg_dsn`` so the production schema is mirrored without
    copy-pasting the DDL into each test file.
    """
    engine = create_async_engine(pg_dsn, future=True)
    try:
        await _install_plan_310b_indexes(engine)
    finally:
        await engine.dispose()
    yield pg_dsn


# ---------------------------------------------------------------------------
# Foundation helpers — shared by Units 2-11 of the 310 test-coverage batch
# ---------------------------------------------------------------------------

# Repo root anchored relative to this file so the helpers don't care about
# the caller's CWD.  ``conftest.py`` lives at
# ``backend/tests/integration/services/data_ingestion/conftest.py`` →
# four parents up to ``backend/``.
_BACKEND_ROOT = Path(__file__).resolve().parents[4]
_FIXTURES_CSV_DIR = _BACKEND_ROOT / "tests" / "fixtures" / "csv"
_SEED_DATA_DIR = _BACKEND_ROOT / "seed_data"


@dataclass(frozen=True)
class SeededYear:
    """Snapshot of the carbon-report tree built by ``seeded_year_with_units``.

    Instances are attached to the session passed into the factory; once
    that session closes, accessing lazy-loaded attributes on these rows
    raises ``DetachedInstanceError``.  Re-fetch by id from a fresh
    session if a test needs to load relationships.  Already-loaded
    scalar columns (``id``, ``module_type_id``, etc.) stay readable.
    """

    year: int
    units: list[Unit] = field(default_factory=list)
    reports_by_unit: dict[int, CarbonReport] = field(default_factory=dict)
    modules_by_unit_and_type: dict[tuple[int, int], CarbonReportModule] = field(
        default_factory=dict
    )


async def seeded_year_with_units(
    session: AsyncSession,
    *,
    year: int,
    n_units: int = 2,
) -> SeededYear:
    """Lay down a year's full carbon-report tree.

    Creates one ``YearConfiguration``, ``n_units`` ``Unit``s (each with
    its own ``CarbonProject`` of type ``CALCULATOR``), one
    ``CarbonReport`` per unit, and one ``CarbonReportModule`` per
    ``(unit, ModuleTypeEnum)`` pair (every member of
    ``ALL_MODULE_TYPE_IDS`` — which today is every ``ModuleTypeEnum``
    value with no "active" filter).  Tests that need a "real" carbon-report
    tree to drive aggregation, recalc, or stats writes against should
    use this rather than hand-rolling.

    Returns a frozen ``SeededYear`` exposing dicts keyed by ``unit_id``
    and ``(unit_id, module_type_id)`` for O(1) lookup.

    Parameters
    ----------
    session
        Caller's ``AsyncSession``.  The helper commits before returning
        so subsequent reads from a different session see the rows.
    year
        Year stamped on the ``YearConfiguration`` and every
        ``CarbonReport``.
    n_units
        Number of units (and therefore reports) to create.  Default 2 —
        the minimum that exercises per-unit module rollups.
    """
    if n_units < 1:
        raise ValueError(f"n_units must be >= 1; got {n_units}")

    # ── 1. Year configuration row (idempotent — a previous test on the
    #       same session may already have laid this year down).
    existing_year = await session.get(YearConfiguration, year)
    if existing_year is None:
        session.add(YearConfiguration(year=year, is_started=True))
        await session.flush()

    units: list[Unit] = []
    reports_by_unit: dict[int, CarbonReport] = {}
    modules_by_unit_and_type: dict[tuple[int, int], CarbonReportModule] = {}

    suffix = uuid4().hex[:8]
    for i in range(n_units):
        unit = Unit(
            provider=UserProvider.DEFAULT,
            institutional_code=f"SEED-{suffix}-{i}",
            institutional_id=f"SEED-ID-{suffix}-{i}",
            name=f"Seed Unit {suffix}-{i}",
            level=2,
            is_active=True,
        )
        session.add(unit)
        await session.flush()
        units.append(unit)

        project = CarbonProject(
            unit_id=unit.id,
            carbon_report_type=CarbonReportType.CALCULATOR,
        )
        session.add(project)
        await session.flush()

        report = CarbonReport(
            year=year,
            unit_id=unit.id,
            carbon_project_id=project.id,
        )
        session.add(report)
        await session.flush()
        reports_by_unit[unit.id] = report

        for mt in ALL_MODULE_TYPE_IDS:
            crm = CarbonReportModule(
                carbon_report_id=report.id,
                module_type_id=int(mt),
            )
            session.add(crm)
            await session.flush()
            modules_by_unit_and_type[(unit.id, int(mt))] = crm

    await session.commit()

    return SeededYear(
        year=year,
        units=units,
        reports_by_unit=reports_by_unit,
        modules_by_unit_and_type=modules_by_unit_and_type,
    )


def _diff_subset(expected: Any, actual: Any, path: str = "$") -> Optional[str]:
    """Return a human-readable diff path when ``actual`` does not contain
    every key/value in ``expected``; ``None`` when the subset matches.

    Recursive subset semantics: dicts in ``expected`` must have every
    key match recursively in ``actual`` (extra keys in ``actual`` are
    fine — that's what "subset" buys callers who don't want to pin
    every column).  Scalars and lists must equal exactly.

    A small in-tree diff is intentional: ``deepdiff`` isn't a runtime
    dep and pulling it in for one assertion would bloat the test
    image.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return f"{path}: expected dict, got {type(actual).__name__} ({actual!r})"
        for key, sub_expected in expected.items():
            if key not in actual:
                return f"{path}.{key}: missing (actual keys: {sorted(actual)})"
            sub = _diff_subset(sub_expected, actual[key], f"{path}.{key}")
            if sub is not None:
                return sub
        return None
    if expected != actual:
        return f"{path}: expected {expected!r}, got {actual!r}"
    return None


async def assert_stats_match(
    session: AsyncSession,
    module_id: int,
    expected: dict,
) -> None:
    """Read ``carbon_report_modules.stats`` for ``module_id`` and assert
    every key/value in ``expected`` is present (recursive subset match).

    Raises ``AssertionError`` with a precise dotted path on the first
    mismatch — e.g.
    ``stats[module_id=42].by_emission_type.5: missing``.

    Pass ``expected={}`` to assert that ``stats`` is at least a dict
    (handy for "shape is right, values come later" smoke checks).
    """
    crm = await session.get(CarbonReportModule, module_id)
    if crm is None:
        raise AssertionError(f"CarbonReportModule id={module_id} not found")

    stats = crm.stats
    if stats is None:
        raise AssertionError(
            f"CarbonReportModule id={module_id}.stats is None — "
            f"expected at least {expected!r}"
        )
    if not isinstance(stats, dict):
        raise AssertionError(
            f"CarbonReportModule id={module_id}.stats is "
            f"{type(stats).__name__}, expected dict"
        )

    diff = _diff_subset(expected, stats, f"stats[module_id={module_id}]")
    if diff is not None:
        raise AssertionError(f"stats mismatch — {diff}\nactual: {stats!r}")


# ``csv_fixture_path``: maps (module, kind) to a Path.  ``seed_data/`` is
# gitignored, so we prefer a trimmed committed fixture under
# ``tests/fixtures/csv/`` whenever one exists; otherwise fall back to the
# flat seed file.  Spec described nested ``seed_data/<module>/<file>.csv``
# but the repo's actual layout is flat — we follow the truth.
#
# The trimmed-fixture map is the single source for "this CI-safe smoke
# CSV exists for that (module, kind)".  Keep entries here as Units 2-11
# add new minimal fixtures.
_TRIMMED_CSV_FIXTURES: dict[tuple[str, str], str] = {
    ("headcount", "data"): "headcount_smoke.csv",
    # Unit 4 — professional_travel
    ("travel_planes", "data"): "travel_planes_smoke.csv",
    ("travel_planes", "unknown_iata"): "travel_planes_unknown_iata.csv",
    ("travel_trains", "data"): "travel_trains_smoke.csv",
    ("travel_trains", "unknown_station"): "travel_trains_unknown_station.csv",
    # Unit 2 — standard MODULE_PER_YEAR CSV ingest matrix.  Each fixture
    # is a template: ``{unit_institutional_id}`` placeholders are
    # rendered at test time via ``str.format`` so the row's unit lookup
    # binds to the seeded ``Unit.institutional_id``.
    ("equipments", "data"): "equipments_smoke.csv",
    ("purchases_common", "data"): "purchases_common_smoke.csv",
    ("external_clouds", "data"): "external_clouds_smoke.csv",
    ("processemissions", "data"): "process_emissions_smoke.csv",
    ("researchfacilities_common", "data"): "researchfacilities_common_smoke.csv",
    # Unit 3 — buildings (energy combustion + rooms)
    ("buildings_energycombustions", "data"): "building_energycombustions_smoke.csv",
    ("building_rooms", "data"): "building_rooms_smoke.csv",
}

# Flat-seed fallback map.  Keys mirror the spec's ``(module, kind)``;
# values are the basename within ``backend/seed_data/``.  Add entries as
# Units 2-11 surface new modules.
_SEED_CSV_BASENAMES: dict[tuple[str, str], str] = {
    ("headcount", "data"): "headcount_data.csv",
    ("headcount", "test"): "headcount_test.csv",
    ("headcount", "template"): "headcount_template.csv",
    ("headcount", "member_factors"): "headcount_member_factors.csv",
    ("headcount", "students_factors"): "headcount_students_factors.csv",
    ("travel_planes", "data"): "travel_planes_data.csv",
    ("travel_planes", "factors"): "travel_planes_factors.csv",
    ("travel_planes", "test"): "travel_planes_test.csv",
    ("travel_trains", "data"): "travel_trains_data.csv",
    ("travel_trains", "factors"): "travel_trains_factors.csv",
    ("equipments", "data"): "equipments_data.csv",
    ("equipments", "factors"): "equipments_factors.csv",
    ("equipments", "data_10lines"): "equipments_data_10lines.csv",
    ("buildings_energycombustions", "data"): ("building_energycombustions_data.csv"),
    ("buildings_energycombustions", "factors"): (
        "building_energycombustions_factors.csv"
    ),
    ("building_rooms", "data"): "building_rooms_data.csv",
    ("building_rooms", "factors"): "building_rooms_factors.csv",
    ("processemissions", "data"): "processemissions_data.csv",
    ("processemissions", "factors"): "processemissions_factors.csv",
    ("external_clouds", "data"): "external_clouds_data.csv",
    ("external_clouds", "factors"): "external_clouds_factors.csv",
    ("external_ai", "data"): "external_ai_data.csv",
    ("external_ai", "factors"): "external_ai_factors.csv",
    ("purchases_common", "data"): "purchases_common_data.csv",
    ("purchases_common", "factors"): "purchases_common_factors.csv",
    ("researchfacilities_common", "data"): "researchfacilities_common_data.csv",
    ("researchfacilities_common", "factors"): "researchfacilities_common_factors.csv",
    ("researchfacilities_animals", "data"): "researchfacilities_animals_data.csv",
    ("researchfacilities_animals", "factors"): "researchfacilities_animals_factors.csv",
}


def csv_fixture_path(module: str, kind: str) -> Path:
    """Resolve ``(module, kind)`` to an absolute CSV path.

    Resolution order:
      1. ``backend/tests/fixtures/csv/<trimmed-name>`` if a trimmed
         committed fixture exists for the pair (CI-safe path).
      2. ``backend/seed_data/<flat-basename>.csv`` if it exists locally
         (gitignored, dev-only — CI runs that need this should ship a
         trimmed fixture instead).

    Raises
    ------
    KeyError
        ``(module, kind)`` has no canonical seed mapping in either the
        trimmed-fixture or seed-data tables.  Add it to one of the maps
        in ``conftest.py``.
    FileNotFoundError
        The mapping exists but neither candidate path is on disk.
    """
    key = (module, kind)
    candidates: list[Path] = []
    if key in _TRIMMED_CSV_FIXTURES:
        candidates.append(_FIXTURES_CSV_DIR / _TRIMMED_CSV_FIXTURES[key])
    if key in _SEED_CSV_BASENAMES:
        candidates.append(_SEED_DATA_DIR / _SEED_CSV_BASENAMES[key])
    if not candidates:
        raise KeyError(
            f"csv_fixture_path: no canonical CSV registered for {key!r}.  "
            f"Add it to _TRIMMED_CSV_FIXTURES (CI) or _SEED_CSV_BASENAMES "
            f"(dev-only) in conftest.py."
        )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"csv_fixture_path: {key!r} is registered but no file found.  "
        f"Tried: {[str(p) for p in candidates]}"
    )


async def dispatch_csv_and_wait(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    file_path: Path | str,
    target_type: TargetType,
    module_type_id: int,
    data_entry_type_id: int,
    year: int,
    ingestion_method: IngestionMethod = IngestionMethod.csv,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.05,
    provider_class: type,
) -> tuple[DataIngestionJob, list[DataIngestionJob]]:
    """Drive a CSV ingest end-to-end against the test PG session factory.

    This is the hot path Units 2-11 share for chain-aware tests: create
    the parent ``csv_ingest`` row, run its handler, then drain every
    chained child ``run_job`` synchronously against ``session_factory``
    rather than the runner's production ``app.db.SessionLocal`` (which
    would point at the wrong DB and never write the rows the test
    inspects).

    Why we don't POST to ``/v1/sync/dispatch``: the runner opens its own
    sessions on ``SessionLocal()``; the test PG would never see what
    those connections write.  Patching ``SessionLocal`` per call site
    is a fragility tax; this helper centralises the proven pattern from
    ``test_full_dag_pipeline_pg.py``.

    Parameters
    ----------
    session_factory
        ``async_sessionmaker`` bound to the test's PG engine.  Children
        run through this so all writes land where ``assert_stats_match``
        and friends will read them.
    file_path
        On-disk CSV.  Resolved via ``csv_fixture_path`` upstream by the
        caller.  Stamped into the parent job's ``meta['config']['file_path']``
        — providers read it from there, not from a kwarg.
    target_type, module_type_id, data_entry_type_id, year, ingestion_method
        Job scope columns; see ``DataIngestionJob``.
    timeout_seconds
        Hard cap on the parent → children drain.  Each iteration sleeps
        ``poll_interval`` between checks.  Raises ``TimeoutError`` if the
        chain doesn't terminate in time.
    poll_interval
        Time between drain-loop iterations.  Default 50ms — short enough
        to keep the smoke test under a second, long enough not to spin.
    provider_class
        Substitute for ``ProviderFactory.get_provider_class`` — required.
        ``meta['provider_name']`` is derived from ``provider_class.__name__``
        so the patched factory and the meta always agree.  Callers that
        only want to assert chain wiring (not actual CSV parsing) pass a
        stub like ``_stub_csv_provider()``; callers that want the real
        provider import + reference it directly.

    Returns
    -------
    (parent_job, [children])
        ``parent_job`` is the post-handler row reloaded from a fresh
        session (state == FINISHED on success).  ``children`` is every
        row sharing ``parent_job.pipeline_id`` ordered by id, EXCLUDING
        the parent itself, so callers can index by ``job_type``.
    """
    from app.tasks import _chain as chain_mod
    from app.tasks import ingestion_tasks as ingest_mod
    from app.tasks.bootstrap import bootstrap_handlers
    from app.tasks.registry import get_handler

    # Force-import every handler module so ``@register("…")`` decorators
    # have populated the registry before we call ``get_handler``.  The
    # production runner calls this on first dispatch; tests need it
    # explicit because they bypass the runner.
    bootstrap_handlers()

    pipeline_id = uuid4()
    parent = DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=year,
        target_type=target_type,
        ingestion_method=ingestion_method,
        provider=UserProvider.DEFAULT,
        state=IngestionState.RUNNING,
        is_current=True,
        job_type="csv_ingest",
        pipeline_id=pipeline_id,
        meta={
            "config": {
                "file_path": str(file_path),
                "module_type_id": int(module_type_id),
                "data_entry_type_id": int(data_entry_type_id),
                "year": year,
            },
            "provider_name": provider_class.__name__,
        },
    )

    async with session_factory() as session:
        # Mirror production ``claim_job`` semantics: demote any prior
        # ``is_current=True`` row sharing this scope BEFORE inserting the
        # new parent.  Without this, a second dispatch on the same
        # ``(module, det, target, method, year)`` trips the partial unique
        # index ``ix_data_ingestion_jobs_is_current_unique``.  Units 4, 5,
        # 8 each rolled their own ad-hoc demote — promoted here so callers
        # don't have to.  Idempotent: rowcount==0 on first dispatch is fine.
        await session.execute(
            text(
                """
                UPDATE data_ingestion_jobs
                SET is_current = false
                WHERE is_current = true
                  AND module_type_id = :module_type_id
                  AND data_entry_type_id = :data_entry_type_id
                  AND target_type = :target_type
                  AND ingestion_method = :ingestion_method
                  AND year = :year
                """
            ),
            {
                "module_type_id": int(module_type_id),
                "data_entry_type_id": int(data_entry_type_id),
                "target_type": target_type.name,
                "ingestion_method": ingestion_method.name,
                "year": year,
            },
        )
        session.add(parent)
        await session.commit()
        await session.refresh(parent)
        parent_id = parent.id

    # Queue child ids via a fire_and_forget shim so the chain can be
    # drained synchronously against the test's PG session factory rather
    # than the runner's production SessionLocal.
    pending: list[int] = []

    def _sync_fire_and_forget(coro: Awaitable[Any], *, name: Optional[str] = None):
        # Close the original run_job coroutine — it would have run on
        # the runner's session factory (production DB) and our test PG
        # would never see it.
        coro.close()  # type: ignore[union-attr]
        if name and name.startswith("run_job-"):
            child_id = int(name.split("-", 1)[1])
            pending.append(child_id)
        return MagicMock()

    async def _run_one_job(job_id: int) -> None:
        """Run one queued job (parent or child) against the test PG.

        Mirrors the runner's claim-then-finalize shape: load the row,
        invoke its handler, **commit the data session** (handlers like
        ``aggregation`` only ``flush()`` and rely on the runner to
        commit), then write FINISHED + result + meta back to the job
        row.  Without the data-session commit, every chained handler
        would silently drop its domain writes — Units 2-11's
        ``assert_stats_match`` calls would then read pre-handler state.
        On exception we roll back the data session and re-raise; the
        helper's caller is the test, which should fail loudly.
        """
        async with session_factory() as job_session:
            row = await job_session.get(DataIngestionJob, job_id)
            if row is None:
                return
            handler = get_handler(row.job_type)
            async with session_factory() as data_session:
                try:
                    meta = await handler(row, job_session, data_session)
                except Exception:
                    await data_session.rollback()
                    raise
                await data_session.commit()
            row.state = IngestionState.FINISHED
            row.result = meta.get("result", IngestionResult.SUCCESS)
            row.status_message = meta.get("status_message", "")
            existing_meta = dict(row.meta or {})
            existing_meta.update({k: v for k, v in meta.items() if k != "result"})
            row.meta = existing_meta
            job_session.add(row)
            await job_session.commit()

    deadline = time.time() + timeout_seconds

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch.object(
                chain_mod, "fire_and_forget", side_effect=_sync_fire_and_forget
            )
        )
        # ``provider_class`` is keyword-only required (see signature) — no
        # None branch needed.
        stack.enter_context(
            patch.object(
                ingest_mod.ProviderFactory,
                "get_provider_class",
                return_value=provider_class,
            )
        )

        # 1. Drive the parent csv_ingest.
        await _run_one_job(parent_id)

        # 2. Drain every chained child breadth-first.  Each child may
        #    enqueue its own child via the same shim; the patches stay
        #    in scope for the entire drain.
        while pending:
            if time.time() > deadline:
                raise TimeoutError(
                    f"dispatch_csv_and_wait: chain did not finish — "
                    f"{len(pending)} child(ren) still queued after "
                    f"{timeout_seconds}s"
                )
            child_id = pending.pop(0)
            await _run_one_job(child_id)
            # Yield so any concurrent awaits (none here, but defensive)
            # get a chance to run.
            await asyncio.sleep(poll_interval if pending else 0)

    # Reload the parent + every job in the pipeline.
    async with session_factory() as session:
        result = await session.execute(
            select(DataIngestionJob)
            .where(DataIngestionJob.pipeline_id == pipeline_id)
            .order_by(DataIngestionJob.id.asc())
        )
        all_rows = list(result.scalars().all())

    parent_row = next((r for r in all_rows if r.id == parent_id), None)
    if parent_row is None:
        raise RuntimeError(
            f"dispatch_csv_and_wait: parent job_id={parent_id} disappeared"
        )
    children = [r for r in all_rows if r.id != parent_id]
    return parent_row, children
