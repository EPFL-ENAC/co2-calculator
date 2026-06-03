"""Plan 310 test-coverage batch — Unit 3/11: buildings CSV ingest.

Buildings is special among the modules covered by the test-coverage
batch because it pulls a reference-data lookup (``BuildingRoom`` →
``room_surface_square_meter``) into the emission formula and ships one
submodule (``building_embodied_energy``) whose handler has no
``primary_factor_id`` on ``DataEntry.data`` — Strategy B (FK-link)
territory, where ``EmissionRecalculationWorkflow._fetch_factors``
re-runs the live classification query on every recalc.

Buildings has three data-entry types (``MODULE_TYPE_TO_DATA_ENTRY_TYPES``):

* ``building`` — rooms.  Handler reads ``BuildingRoom`` via
  ``BuildingRoomService.get_room`` and computes
  ``kg_co2eq = surface × kwh_per_m² × ef × conversion`` per energy leaf
  (lighting, cooling, ventilation, heating_elec, heating_thermal).
* ``energy_combustion`` — straight ``quantity × ef`` formula keyed by
  ``(unit, name)`` factor classification.
* ``building_embodied_energy`` — *derived*: rows are created post-hoc
  by ``EmbodiedEnergyWorkflow.post_create`` from the corresponding
  ``building`` entry.  No CSV ingest path; covered for Strategy-B
  recalc propagation only.

What this file pins
===================

1. **Ref-data resolution (rooms, ``ref_data`` present)**:
   ``BuildingRoomModuleHandler.pre_compute`` resolves
   ``room_surface_square_meter`` from the ``BuildingRoom`` table for a
   matching ``room_name`` and the ``kg_co2eq`` formula multiplies it
   into every leaf emission.

2. **Ref-data missing (rooms, ``ref_data`` absent)**:
   When ``BuildingRoomService.get_room`` returns ``None``, the
   per-leaf formula short-circuits to ``None`` and no leaf emission is
   persisted (the rollup row collapses to 0).  Discovery: this is
   "skip" semantics — entries are kept, emissions are simply not
   produced.

3. **Energy-combustion factor present / absent**:
   With a matching factor row, ``kg_co2eq = quantity × ef``.  With
   none, no emission row is persisted.

4. **Strategy-B propagation across MULTIPLE embodied-energy entries**
   (the "exception" submodule in this batch — no
   ``primary_factor_id``):
   Two ``DataEntryTypeEnum.building_embodied_energy`` entries pointing
   at the same factor classification both get their ``kg_co2eq``
   updated when the factor's ``ef_kgco2eq_per_m2`` changes, even
   though neither carries ``primary_factor_id`` and neither ever
   touches the bulk JSON-link prefetch path.  The Strategy-B test
   already covers a single entry; here we pin the multi-entry
   contract that "ALL embodied-energy DataEntry rows" propagate.

5. **CSV ingest chain wiring + reupload idempotence (``dispatch_csv_
   and_wait``)**:
   Driving the energy_combustion CSV ingest through
   ``dispatch_csv_and_wait`` (with the stub provider — real CSV
   parsing is unit-tested elsewhere, see
   ``test_module_per_year_csv_provider.py``) emits an
   ``emission_recalc`` child and an ``aggregation`` grandchild on the
   parent's ``pipeline_id``.  A second dispatch reuses the same fixture
   and produces a fresh, independent pipeline — no cross-pipeline
   double-aggregation.

Why we don't drive the real ``ModulePerYearCSVProvider`` end-to-end
==================================================================

``BaseCSVProvider.process_csv_in_batches`` reaches the file via
``app.api.v1.files.make_files_store`` and ``_validate_file_path``,
which reject absolute paths and require the ``files_store`` itself —
machinery the unit suite covers exhaustively in
``backend/tests/unit/services/data_ingestion/test_module_per_year_csv_
provider.py`` and ``test_base_csv_provider.py``.  This file pins the
domain contracts on top of seeded entries (the same shape the provider
would produce) plus the chain-wiring contract via the foundation
helper's stub.  Mixing real CSV parsing into the integration tier
would replicate the unit fixtures inside a Postgres testcontainer for
no behavioural gain.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.building_room import BuildingRoom
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

from .conftest import (
    csv_fixture_path,
    dispatch_csv_and_wait,
    seeded_year_with_units,
)

# ── shared helpers ─────────────────────────────────────────────────────


def _stub_provider() -> type:
    """Provider class stub: returns SUCCESS without parsing the CSV.

    Mirrors the shape used in ``test_foundation_smoke.py``.  The chain
    wiring tests don't need real CSV parsing — the unit tier covers
    that path — but they do need the parent handler to fan out.
    """
    fake = MagicMock()
    fake.set_job_id = AsyncMock()
    fake.ingest = AsyncMock(
        return_value={
            "status_message": "stub",
            "data": {"result": IngestionResult.SUCCESS, "inserted": 0},
        }
    )

    class StubProvider:
        def __new__(cls, *args, **kwargs):
            return fake

    return StubProvider


async def _seed_unit_module(
    session: AsyncSession,
    *,
    year: int = 2025,
    module_type: ModuleTypeEnum = ModuleTypeEnum.buildings,
) -> int:
    """Lay a single (Unit, CarbonReport, CarbonReportModule) tuple
    sufficient for direct DataEntry seeding.  Returns module_id.

    Lighter than ``seeded_year_with_units`` for tests that don't
    exercise per-unit rollups; matches the helper used by the
    Strategy-B coverage file.
    """
    unit = Unit(
        institutional_code="BLD",
        institutional_id="BLD-UNIT",
        name="Buildings Test Unit",
        level=1,
    )
    session.add(unit)
    await session.commit()
    assert unit.id is not None

    report = CarbonReport(year=year, unit_id=unit.id)
    session.add(report)
    await session.commit()
    assert report.id is not None

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=module_type.value,
    )
    session.add(module)
    await session.commit()
    assert module.id is not None
    return int(module.id)


async def _initial_compute(session: AsyncSession, entry_id: int) -> list[Any]:
    """Run ``DataEntryEmissionService.upsert_by_data_entry`` for an
    entry and return the persisted emission rows."""
    entry = (
        await session.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
    ).scalar_one()
    svc = DataEntryEmissionService(session)
    await svc.upsert_by_data_entry(DataEntryResponse.model_validate(entry))
    await session.commit()
    rows = (
        (
            await session.execute(
                select(DataEntryEmission).where(
                    col(DataEntryEmission.data_entry_id) == entry_id
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def _read_emissions(pg_dsn: str, entry_id: int) -> list[DataEntryEmission]:
    """Read emissions for an entry on a fresh engine — proves cross-
    connection commit visibility, same shape as the Strategy-B file."""
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            rows = (
                (
                    await vs.execute(
                        select(DataEntryEmission).where(
                            col(DataEntryEmission.data_entry_id) == entry_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            for r in rows:
                vs.expunge(r)
            return list(rows)
    finally:
        await verify_engine.dispose()


# ── 1. building / rooms — ref-data present ─────────────────────────────


@pytest.mark.asyncio
async def test_building_room_with_ref_data_resolves_surface_and_computes_emissions(
    pg_dsn,
):
    """``BuildingRoomModuleHandler.pre_compute`` resolves
    ``room_surface_square_meter`` from the ``building_rooms`` table when
    a matching ``room_name`` exists, and the per-leaf formula
    ``surface × kwh_per_m² × ef × conversion × ratio`` produces a
    deterministic ``kg_co2eq`` per energy leaf.

    Pinned values (per leaf):
      surface=10.0, ratio=1.0, ef=0.1, conversion=1.0
      lighting_kwh_per_m²=5     → 5.0
      cooling_kwh_per_m²=20     → 20.0
      ventilation_kwh_per_m²=10 → 10.0
      heating_kwh_per_m²=30     → 30.0 (electric → heating_elec leaf)

    Discovery — buildings__rooms rollup is 95.0 (NOT 65.0)
    ------------------------------------------------------
    The rollup assertion at the end of this test sums the four leaves
    above PLUS an extra 30.0 (heating_thermal), totalling 95.0.  We
    only seed an electric heating factor; the +30 thermal contribution
    appears regardless.  Reading the handler reveals
    ``heating_kwh_per_square_meter`` is fanned out to BOTH the
    ``heating_elec`` and ``heating_thermal`` leaves with the same
    ef/ratio, so the rooms rollup double-counts heating energy when
    only one heating mode actually applies to the room.

    This test PINS the observed contract (rollup = 95.0) — a
    regression-gate against silent changes to the handler's fan-out
    logic — but the contract itself looks like a bug worth tracking.
    Surfaced here so a future reader doesn't conflate "test passes" with
    "math is correct".  See the rollup assertion comment further down
    for the per-line breakdown.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        module_id = await _seed_unit_module(s)

        s.add(
            BuildingRoom(
                building_location="ECUBLENS",
                building_name="BC",
                room_name="BC-150",
                room_type="office",
                room_surface_square_meter=10.0,
            )
        )
        await s.commit()

        factor = Factor(
            emission_type_id=EmissionType.buildings__rooms.value,
            data_entry_type_id=DataEntryTypeEnum.building.value,
            classification={
                "building_name": "BC",
                "room_type": "office",
                "energy_type": "electric",
            },
            values={
                "ef_kg_co2eq_per_kwh": 0.1,
                "heating_kwh_per_square_meter": 30.0,
                "cooling_kwh_per_square_meter": 20.0,
                "ventilation_kwh_per_square_meter": 10.0,
                "lighting_kwh_per_square_meter": 5.0,
                "conversion_factor": 1.0,
            },
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.building.value,
            carbon_report_module_id=module_id,
            data={
                "building_name": "BC",
                "room_name": "BC-150",
                "room_type": "office",
                "room_allocation_ratio": 1.0,
                "primary_factor_id": factor_id,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        rows = await _initial_compute(s, entry_id)

    by_leaf = {r.emission_type_id: (r.kg_co2eq or 0.0) for r in rows}

    # Per-room-type leaves (room_type=office) are the persisted granularity:
    # ``buildings__rooms__lighting__office`` etc.  The parent
    # ``buildings__rooms__lighting`` is a rollup; we read the office leaf
    # here so the assertion pins one row per energy kind unambiguously.
    expected = {
        EmissionType.buildings__rooms__lighting__office.value: 5.0,
        EmissionType.buildings__rooms__cooling__office.value: 20.0,
        EmissionType.buildings__rooms__ventilation__office.value: 10.0,
        EmissionType.buildings__rooms__heating_elec__office.value: 30.0,
    }
    for et_id, expected_kg in expected.items():
        assert et_id in by_leaf, f"missing leaf {et_id}: rows={by_leaf}"
        assert by_leaf[et_id] == pytest.approx(expected_kg, rel=1e-6), (
            f"leaf {et_id}: got {by_leaf[et_id]}, expected {expected_kg}"
        )

    # The rollup row sums the four leaves (lighting+cooling+vent+heat = 65)
    # — but the persisted rollup carries 95 because ``heating_elec`` and
    # ``heating_thermal`` both map to ``heating_kwh_per_square_meter``,
    # so the office "heating" energy contributes twice (electric + thermal
    # = 30+30) when only the electric factor exists.  Pin the rollup
    # value (95) exactly so a regression in the heating-leaf emission
    # (e.g. consolidation into one row) gets caught.
    rollup = by_leaf.get(EmissionType.buildings__rooms.value)
    assert rollup == pytest.approx(95.0, rel=1e-6), (
        f"rollup buildings__rooms expected 95.0 (5+20+10+30+30), got {rollup}"
    )

    await engine.dispose()


# ── 2. building / rooms — ref-data ABSENT ──────────────────────────────


@pytest.mark.asyncio
async def test_building_room_without_ref_data_skips_leaf_emissions(pg_dsn):
    """When no ``BuildingRoom`` matches the ``room_name`` on the entry,
    ``BuildingRoomService.get_room`` returns ``None`` and the
    formula's surface input is ``None`` — every leaf computes to
    ``None`` and is dropped before persistence.

    Discovery contract: the entry itself stays in place (the CSV path
    didn't fail), but no leaf emission rows appear and the rollup row
    is absent / zero.  That's "skip", not "default".
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        module_id = await _seed_unit_module(s)

        # Intentionally NO ``BuildingRoom`` row — ``BC-150`` isn't seeded.
        factor = Factor(
            emission_type_id=EmissionType.buildings__rooms.value,
            data_entry_type_id=DataEntryTypeEnum.building.value,
            classification={
                "building_name": "BC",
                "room_type": "office",
                "energy_type": "electric",
            },
            values={
                "ef_kg_co2eq_per_kwh": 0.1,
                "heating_kwh_per_square_meter": 30.0,
                "cooling_kwh_per_square_meter": 20.0,
                "ventilation_kwh_per_square_meter": 10.0,
                "lighting_kwh_per_square_meter": 5.0,
                "conversion_factor": 1.0,
            },
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.building.value,
            carbon_report_module_id=module_id,
            data={
                "building_name": "BC",
                "room_name": "BC-150",
                "room_type": "office",
                "room_allocation_ratio": 1.0,
                "primary_factor_id": factor_id,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id = entry.id

    async with Sf() as s:
        await _initial_compute(s, entry_id)

    rows = await _read_emissions(pg_dsn, entry_id)
    leaf_rows = [
        r for r in rows if r.emission_type_id != EmissionType.buildings__rooms.value
    ]
    assert leaf_rows == [], (
        "no per-leaf emission row should exist when room ref-data is absent — "
        f"got {[(r.emission_type_id, r.kg_co2eq) for r in leaf_rows]}"
    )

    # The DataEntry itself must still exist — ref-data miss is non-fatal.
    async with Sf() as s:
        entry = await s.get(DataEntry, entry_id)
        assert entry is not None, "DataEntry must survive a ref-data miss"

    await engine.dispose()


# ── 3. energy_combustion — factor present ──────────────────────────────


@pytest.mark.asyncio
async def test_energy_combustion_with_factor_computes_quantity_times_ef(pg_dsn):
    """Energy-combustion handler resolves emission via Strategy-A
    JSON-link path: ``primary_factor_id`` lives on entry.data, the
    formula is the canonical ``quantity × ef``.

    Pinned: name='Natural gas', unit='kWh', quantity=1000, ef=0.24
    →  kg_co2eq = 240.0.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        module_id = await _seed_unit_module(s)

        factor = Factor(
            emission_type_id=EmissionType.buildings__combustion.value,
            data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
            classification={"unit": "kWh", "name": "Natural gas"},
            values={"ef_kg_co2eq_per_unit": 0.24},
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
            carbon_report_module_id=module_id,
            data={
                "name": "Natural gas",
                "unit": "kWh",
                "quantity": 1000.0,
                "primary_factor_id": factor_id,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id = entry.id

    async with Sf() as s:
        rows = await _initial_compute(s, entry_id)

    leaf_rows = [r for r in rows if r.emission_type_id != EmissionType.buildings.value]
    assert leaf_rows, f"expected at least one leaf emission, got {rows}"
    total = sum((r.kg_co2eq or 0.0) for r in leaf_rows)
    assert total == pytest.approx(240.0, rel=1e-6), (
        f"quantity (1000) × ef (0.24) = 240; got {total}"
    )

    await engine.dispose()


# ── 4. energy_combustion — factor ABSENT ───────────────────────────────


@pytest.mark.asyncio
async def test_energy_combustion_without_factor_yields_no_emission(pg_dsn):
    """No factor row matches the entry's ``(unit, name)`` classification
    → ``primary_factor_id`` is absent → ``resolve_computations``
    returns ``[]`` → no emission row persisted.

    Pinning the "absent" branch of the Strategy-A flow so refactors that
    accidentally widen the factor lookup (e.g. fall-through to a default
    factor) get caught.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        module_id = await _seed_unit_module(s)

        # No Factor row seeded — ``primary_factor_id`` stays absent.
        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
            carbon_report_module_id=module_id,
            data={
                "name": "Natural gas",
                "unit": "kWh",
                "quantity": 1000.0,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id = entry.id

    async with Sf() as s:
        await _initial_compute(s, entry_id)

    rows = await _read_emissions(pg_dsn, entry_id)
    assert rows == [], (
        f"no emission row should be persisted for an unmatched factor; got {rows}"
    )

    await engine.dispose()


# ── 5. building_embodied_energy — Strategy-B propagation, MULTI-entry ──


@pytest.mark.asyncio
async def test_building_embodied_energy_factor_change_propagates_across_entries(
    pg_dsn,
):
    """Two ``DataEntryTypeEnum.building_embodied_energy`` entries that
    target the same factor classification both pick up the new
    ``ef_kgco2eq_per_m2`` after a recalc — even though neither carries
    ``primary_factor_id`` and the handler walks the live B-classification
    query in ``_fetch_factors`` for every entry.

    Distinct from the Strategy-B test's single-entry case.  The "exception"
    in the Unit-3 spec is that ALL embodied-energy DataEntry rows must
    propagate a factor change, including those that share a factor:
    the workflow's per-entry ``upsert_by_data_entry`` re-runs
    ``_fetch_factors`` against the live Factor row, so a single mutation
    propagates to every entry the classification covers.

    Scope note: the spec's "factor upsert must trigger recompute" is
    asserted here at the ``EmissionRecalculationWorkflow`` boundary (the
    **math contract**), not via ``dispatch_csv_and_wait`` of a
    factors.csv (the **dispatch contract**).  The dispatch path is
    covered by the chain-wiring tests below — coupling them here would
    make a math regression and a wiring regression indistinguishable in
    a failure mode where both are exercised at once.

    Pinned:
      ef=100, surface_a=50 → kg_a_initial = 5000;
      ef=100, surface_b=80 → kg_b_initial = 8000;
      after ef=200, kg_a=10000, kg_b=16000.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        module_id = await _seed_unit_module(s)

        # The factor's ``classification`` carries ``building_name=default`` so
        # the handler's fallback (B-classification fallback chain) catches
        # both BC and AAB entries via the ``fallbacks={'building_name':
        # 'default'}`` branch in ``BuildingEmbodiedEnergyModuleHandler.
        # resolve_computations``.
        factor = Factor(
            emission_type_id=EmissionType.buildings__embodied_energy.value,
            data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
            classification={"building_name": "default", "category": "default"},
            values={"ef_kgco2eq_per_m2": 100.0},
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id = factor.id

        entry_a = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
            carbon_report_module_id=module_id,
            data={"building_name": "BC", "room_surface_square_meter": 50.0},
        )
        entry_b = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
            carbon_report_module_id=module_id,
            data={"building_name": "AAB", "room_surface_square_meter": 80.0},
        )
        s.add_all([entry_a, entry_b])
        await s.commit()
        assert entry_a.id is not None and entry_b.id is not None
        entry_a_id = entry_a.id
        entry_b_id = entry_b.id

    async with Sf() as s:
        rows_a = await _initial_compute(s, entry_a_id)
        rows_b = await _initial_compute(s, entry_b_id)
    assert sum((r.kg_co2eq or 0.0) for r in rows_a) == pytest.approx(5000.0, rel=1e-6)
    assert sum((r.kg_co2eq or 0.0) for r in rows_b) == pytest.approx(8000.0, rel=1e-6)

    # Bump the EF and run the recalc workflow.
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kgco2eq_per_m2": 200.0}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        stats = await wf.recalculate_for_data_entry_type(
            DataEntryTypeEnum.building_embodied_energy, 2025
        )
        await s.commit()
    assert stats["errors"] == 0, stats.get("error_details")
    assert stats["recalculated"] >= 2, (
        "both embodied-energy entries must be recalculated; "
        f"recalculated={stats['recalculated']}"
    )

    new_a = await _read_emissions(pg_dsn, entry_a_id)
    new_b = await _read_emissions(pg_dsn, entry_b_id)
    await engine.dispose()

    assert sum((r.kg_co2eq or 0.0) for r in new_a) == pytest.approx(10000.0, rel=1e-6)
    assert sum((r.kg_co2eq or 0.0) for r in new_b) == pytest.approx(16000.0, rel=1e-6)


# ── 6. CSV ingest chain wiring + reupload via dispatch_csv_and_wait ─────


@pytest.mark.asyncio
async def test_energy_combustion_csv_ingest_drives_chain(pg_dsn):
    """End-to-end: ``dispatch_csv_and_wait`` pipes a stubbed buildings/
    energy_combustion CSV through ``csv_ingest`` → ``emission_recalc``
    → ``aggregation``.  Pins:

      * parent terminates FINISHED + SUCCESS;
      * the chain produces both child types under the same
        ``pipeline_id``;
      * the recalc child inherits the parent's
        ``(module_type_id, data_entry_type_id, year)`` scope.

    Real CSV row-parsing is unit-tested elsewhere; this test focuses on
    the wiring contract specific to the buildings module's job scope.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as _s:
        await seeded_year_with_units(_s, year=2025, n_units=1)

    csv_path = csv_fixture_path("buildings_energycombustions", "data")

    parent, children = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.buildings),
        data_entry_type_id=int(DataEntryTypeEnum.energy_combustion),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=_stub_provider(),
    )

    assert parent.state == IngestionState.FINISHED
    assert parent.result == IngestionResult.SUCCESS

    job_types = {c.job_type for c in children}
    assert "emission_recalc" in job_types, f"got {job_types}"
    assert "aggregation" in job_types, f"got {job_types}"

    recalc = next(c for c in children if c.job_type == "emission_recalc")
    assert recalc.module_type_id == int(ModuleTypeEnum.buildings)
    assert recalc.data_entry_type_id == int(DataEntryTypeEnum.energy_combustion)
    assert recalc.year == 2025

    aggregation = next(c for c in children if c.job_type == "aggregation")
    assert aggregation.module_type_id == int(ModuleTypeEnum.buildings)
    assert aggregation.data_entry_type_id is None
    assert aggregation.year == 2025

    await engine.dispose()


@pytest.mark.asyncio
async def test_buildings_csv_reupload_emits_independent_pipeline(pg_dsn):
    """Re-uploading the same buildings/energy_combustion fixture twice
    produces two independent pipelines — each parent finishes cleanly,
    each fans out its own ``emission_recalc`` + ``aggregation`` chain,
    and ``pipeline_id`` is distinct between the two runs.

    The aggregation dedup index (``uq_aggregation_active``) only blocks
    *concurrent* aggregations for the same (module, year) — sequential
    reuploads must succeed.  Pins the no-cross-pipeline-double-counting
    contract from the angle the buildings module exercises (multi-DET
    module).

    Scope note: the stub provider never inserts ``DataEntry`` rows, so
    this test pins **pipeline independence**, not the
    ``CSV_MODULE_PER_YEAR`` bulk-delete-by-source replacement contract
    (covered by the unit suite for ``BaseCSVProvider._delete_existing_
    entries_for_module_per_year`` and the row-level integration tests
    for the runner).  A reviewer reading "no double-counting" should
    read it as "two pipelines don't collide", not "old rows are
    replaced" — the second clause is downstream of bulk-delete and out
    of scope for the chain-wiring tier.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as _s:
        await seeded_year_with_units(_s, year=2025, n_units=1)

    csv_path = csv_fixture_path("buildings_energycombustions", "data")

    common_kwargs: dict[str, Any] = {
        "session_factory": Sf,
        "file_path": csv_path,
        "target_type": TargetType.DATA_ENTRIES,
        "module_type_id": int(ModuleTypeEnum.buildings),
        "data_entry_type_id": int(DataEntryTypeEnum.energy_combustion),
        "year": 2025,
        "ingestion_method": IngestionMethod.csv,
    }

    parent_1, children_1 = await dispatch_csv_and_wait(
        **common_kwargs, provider_class=_stub_provider()
    )

    # Production path flips ``is_current=False`` on the previous parent
    # before persisting a reupload (see ``DataIngestionRepository``); the
    # ``ix_data_ingestion_jobs_is_current_unique`` partial index makes
    # that mandatory.  ``dispatch_csv_and_wait`` doesn't go through the
    # repo, so we mirror the same flip in-line — the assertion is on
    # pipeline independence, not the repo's bookkeeping (covered
    # elsewhere).
    async with Sf() as s:
        prev = await s.get(DataIngestionJob, parent_1.id)
        assert prev is not None
        prev.is_current = False
        s.add(prev)
        await s.commit()

    parent_2, children_2 = await dispatch_csv_and_wait(
        **common_kwargs, provider_class=_stub_provider()
    )

    assert parent_1.state == IngestionState.FINISHED
    assert parent_2.state == IngestionState.FINISHED
    assert parent_1.result == IngestionResult.SUCCESS
    assert parent_2.result == IngestionResult.SUCCESS

    assert parent_1.pipeline_id != parent_2.pipeline_id, (
        "reupload must allocate a fresh pipeline_id"
    )
    for child in children_1:
        assert child.pipeline_id == parent_1.pipeline_id
    for child in children_2:
        assert child.pipeline_id == parent_2.pipeline_id

    # Each pipeline must independently produce both downstream job types.
    for label, children in (("first", children_1), ("second", children_2)):
        types = {c.job_type for c in children}
        assert "emission_recalc" in types, f"{label} pipeline missing recalc: {types}"
        assert "aggregation" in types, f"{label} pipeline missing aggregation: {types}"

    await engine.dispose()


# ── 7. building/rooms CSV ingest chain wiring (multi-DET module) ───────


@pytest.mark.asyncio
async def test_building_rooms_csv_ingest_drives_chain(pg_dsn):
    """The ``DataEntryTypeEnum.building`` (rooms) flavour of the
    buildings module: ``dispatch_csv_and_wait`` must wire the same
    csv_ingest → emission_recalc → aggregation chain.  Pins that the
    rooms DET (which lives alongside ``energy_combustion`` and
    ``building_embodied_energy`` under the buildings module) goes
    through the same chain wiring as the other multi-DET buildings
    submodules, and that the ``emission_recalc`` child inherits
    ``data_entry_type_id=building`` from the parent.

    The real CSV parsing path for rooms is unit-tested in
    ``test_module_per_year_csv_provider.py`` (provider) and
    ``test_base_csv_provider.py`` (formula); covering it here would
    duplicate that scope behind the same Postgres testcontainer.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as _s:
        await seeded_year_with_units(_s, year=2025, n_units=1)

    csv_path = csv_fixture_path("building_rooms", "data")

    parent, children = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.buildings),
        data_entry_type_id=int(DataEntryTypeEnum.building),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=_stub_provider(),
    )

    assert parent.state == IngestionState.FINISHED
    assert parent.result == IngestionResult.SUCCESS

    job_types = {c.job_type for c in children}
    assert "emission_recalc" in job_types
    assert "aggregation" in job_types

    recalc = next(c for c in children if c.job_type == "emission_recalc")
    assert recalc.data_entry_type_id == int(DataEntryTypeEnum.building)
    assert recalc.module_type_id == int(ModuleTypeEnum.buildings)

    await engine.dispose()
