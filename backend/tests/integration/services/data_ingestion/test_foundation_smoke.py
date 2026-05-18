"""Smoke test for the foundation conftest helpers (Plan 310 test-coverage,
Unit 1/11).

Validates that the four helpers added in this PR's conftest compose into a
working end-to-end check:

1. ``seeded_year_with_units`` lays down a year + 2 units + every
   module-type's CRM rows.
2. ``csv_fixture_path`` resolves to the trimmed committed fixture.
3. ``dispatch_csv_and_wait`` drives a stubbed CSV ingest through the chain
   wiring (csv_ingest → emission_recalc → aggregation) against the test
   PG session factory, finishing every link.
4. ``assert_stats_match`` reads ``carbon_report_modules.stats`` after the
   chain.  In the smoke we only require *shape* (a dict), not numeric
   values — Units 2-11 will pin the math against scope-specific
   contracts.

Why a stubbed provider:
The smoke proves the *plumbing* works (fixture composition, chain drive,
stats assertion).  The aggregation handler computes per-module stats
even when the CSV ingest produced no data_entries — a "fresh module
with no entries" snapshot is itself a meaningful contract.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ALL_MODULE_TYPE_IDS, ModuleTypeEnum

from .conftest import (
    SeededYear,
    assert_stats_match,
    csv_fixture_path,
    dispatch_csv_and_wait,
    seeded_year_with_units,
)


async def _install_aggregation_dedup_index(engine) -> None:
    """Mirror the partial unique index Plan 310-D's migration adds.

    ``pg_dsn`` builds tables via ``SQLModel.metadata.create_all``, which
    doesn't run Alembic — so the dedup INSERT in the aggregation chain
    has no index to bind to.  Install it here.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_aggregation_active "
                "ON data_ingestion_jobs (module_type_id, year) "
                "WHERE job_type = 'aggregation' "
                "AND state IN ("
                "'NOT_STARTED'::ingestion_state_enum, "
                "'QUEUED'::ingestion_state_enum, "
                "'RUNNING'::ingestion_state_enum)"
            )
        )


def _stub_csv_provider() -> type:
    """Provider class stub: returns SUCCESS with zero inserts so the
    chain fans out without parsing the CSV.

    Mirrors ``test_full_dag_pipeline_pg.py``'s ``FakeProviderClass``.
    Smoke only needs the chain to fire — Unit 2 onward will swap this
    for the real provider once they pin actual ingestion math.
    """
    fake = MagicMock()
    fake.set_job_id = AsyncMock()
    fake.ingest = AsyncMock(
        return_value={
            "status_message": "smoke-stub",
            "data": {"result": IngestionResult.SUCCESS, "inserted": 0},
        }
    )

    class StubProvider:
        def __new__(cls, *args, **kwargs):
            return fake

    return StubProvider


def test_seeded_year_dataclass_is_frozen() -> None:
    """The helper returns a frozen dataclass — pin that contract so
    Units 2-11 can't accidentally mutate the snapshot."""
    seeded = SeededYear(year=2025)
    with pytest.raises(dataclasses.FrozenInstanceError):
        seeded.year = 2026  # type: ignore[misc]


def test_csv_fixture_path_resolves_committed_smoke_fixture() -> None:
    """``('headcount', 'data')`` must resolve to the committed trimmed
    fixture even when ``backend/seed_data/`` is absent (CI scenario)."""
    path = csv_fixture_path("headcount", "data")
    assert path.is_file(), f"resolved path {path} should exist"
    assert path.suffix == ".csv"


def test_csv_fixture_path_unknown_pair_raises_keyerror() -> None:
    """A ``(module, kind)`` with no mapping raises ``KeyError`` — pin
    the contract so Units 2-11 know they have to register new pairs
    explicitly rather than silently get a missing-file error."""
    with pytest.raises(KeyError):
        csv_fixture_path("nonexistent", "module")


@pytest.mark.asyncio
async def test_seeded_year_with_units_creates_full_tree(pg_dsn) -> None:
    """``seeded_year_with_units`` must persist YearConfiguration + units
    + reports + one CRM per (unit, ModuleTypeEnum)."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=2025, n_units=2)

    assert seeded.year == 2025
    assert len(seeded.units) == 2
    assert len(seeded.reports_by_unit) == 2
    expected_pairs = {
        (u.id, int(mt)) for u in seeded.units for mt in ALL_MODULE_TYPE_IDS
    }
    assert set(seeded.modules_by_unit_and_type.keys()) == expected_pairs

    await engine.dispose()


@pytest.mark.asyncio
async def test_assert_stats_match_diffs_subset(pg_dsn) -> None:
    """``assert_stats_match`` succeeds on subset matches and surfaces
    a clear path on mismatches."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=2026, n_units=1)
        unit_id = seeded.units[0].id
        crm = seeded.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]
        crm.stats = {"total": 100.0, "by_emission_type": {"1": 60.0, "2": 40.0}}
        s.add(crm)
        await s.commit()
        crm_id = crm.id

    async with Sf() as s:
        # Exact subset — passes.
        await assert_stats_match(s, crm_id, {"total": 100.0})
        # Nested subset — passes.
        await assert_stats_match(s, crm_id, {"by_emission_type": {"1": 60.0}})

        # Wrong scalar value — raises.
        with pytest.raises(AssertionError, match="total"):
            await assert_stats_match(s, crm_id, {"total": 999.0})

        # Missing nested key — raises with dotted path.
        with pytest.raises(AssertionError, match="by_emission_type"):
            await assert_stats_match(
                s, crm_id, {"by_emission_type": {"missing_key": 0.0}}
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_dispatch_csv_and_wait_drives_full_chain(pg_dsn_with_310b) -> None:
    """End-to-end smoke: seed the tree, dispatch a stubbed headcount
    CSV ingest, wait for the chain to FINISH, and assert the stats
    column exists on the targeted CRM.

    Asserts on *shape* (dict, expected keys present), NOT numeric
    values — Units 2-11 will pin the math against scope-specific
    contracts.
    """
    engine = create_async_engine(pg_dsn_with_310b, future=True)
    await _install_aggregation_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=2025, n_units=1)

    csv_path = csv_fixture_path("headcount", "data")

    parent, children = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=_stub_csv_provider(),
    )

    # Parent must terminate cleanly.
    assert parent.state == IngestionState.FINISHED, (
        f"csv_ingest parent did not finish: state={parent.state}"
    )
    assert parent.result == IngestionResult.SUCCESS, (
        f"csv_ingest parent reported {parent.result}"
    )

    # Chain must have at least one emission_recalc child.  The
    # aggregation grandchild is module-scoped and may dedup against
    # itself across the chain — assert weakly here.
    job_types = {c.job_type for c in children}
    assert "emission_recalc" in job_types, (
        f"expected emission_recalc child; got job_types={job_types}"
    )

    # ``assert_stats_match`` against the CRM the recalc/aggregation
    # touched: the headcount module for the seeded unit.  After the
    # aggregation child runs, the CRM's ``stats`` column MUST be a
    # dict — aggregation runs even on empty data and writes a
    # zero-shape stats payload.  A ``None`` here would mean
    # ``data_session`` never committed (regression of the
    # ``_run_one_job`` commit fix).
    unit_id = seeded.units[0].id
    crm = seeded.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]
    async with Sf() as s:
        result = await s.execute(
            sa_select(CarbonReportModule).where(CarbonReportModule.id == crm.id)
        )
        fresh = result.scalar_one()
        assert isinstance(fresh.stats, dict), (
            f"aggregation should leave stats as a dict; got {fresh.stats!r}. "
            "Most likely cause: dispatch_csv_and_wait._run_one_job stopped "
            "committing data_session — handlers' domain writes never "
            "persisted past their session scope."
        )
        # Empty subset asserts the dict shape; Units 2-11 will pin
        # specific keys + numerics.
        await assert_stats_match(s, crm.id, {})

    await engine.dispose()
