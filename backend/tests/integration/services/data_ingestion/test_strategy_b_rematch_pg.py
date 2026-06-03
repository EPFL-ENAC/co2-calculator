"""Plan 310-D follow-up — Strategy B (FK-link) rematch coverage.

Plan 310-D's batch rematch in ``EmissionRecalculationWorkflow`` only walks
``factor_lookup`` for handlers whose ``kind_field`` is present on
``entry.data`` (the JSON-link path).  Handlers whose factor link only ever
lives on ``data_entry_emissions.primary_factor_id`` (the FK-link path) —
travel/plane, travel/train, headcount/member, headcount/student, building
embodied energy — never enter that branch and were assumed to be skipped.

In practice, the existing per-entry ``upsert_by_data_entry`` →
``prepare_create`` → ``_fetch_factors`` chain already re-runs the live
Strategy B classification query (``data_entry_emission_service.py:343-415``)
for every entry on every recalc.  So a CSV reupload that changes a
factor's ``values`` dict propagates retroactively without needing a
second walk over ``data_entry_emissions``.

This file documents the contract per FK-link module.  Each test:

1. Seeds a unit / report / module / factor / data entry.
2. Computes the initial emission via ``DataEntryEmissionService``.
3. Mutates ``factor.values`` (changing the EF, never the classification).
4. Calls ``EmissionRecalculationWorkflow.recalculate_for_data_entry_type``.
5. Asserts the persisted ``DataEntryEmission.kg_co2eq`` reflects the new
   EF on a **separate engine** (proves cross-connection commit
   visibility).

For the strict-drop variant, the factor row itself is deleted (not
re-classified) so ``_fetch_factors`` returns ``[]``.  The contract is the
same as Strategy A's strict-drop in PR #1027: the data_entry_emission
rows for the entry are deleted and module stats refreshed.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

# ── Helpers ────────────────────────────────────────────────────────────


async def _seed_unit_and_module(
    session: AsyncSession,
    *,
    module_type: ModuleTypeEnum,
    year: int = 2025,
) -> tuple[int, int]:
    """Create a Unit + CarbonReport + CarbonReportModule, returning ids."""
    unit = Unit(
        institutional_code="TEST",
        institutional_id="TEST-UNIT",
        name="Test Unit",
        level=1,
    )
    session.add(unit)
    await session.commit()
    assert unit.id is not None
    unit_id: int = unit.id

    report = CarbonReport(year=year, unit_id=unit_id)
    session.add(report)
    await session.commit()
    assert report.id is not None
    report_id: int = report.id

    module = CarbonReportModule(
        carbon_report_id=report_id,
        module_type_id=module_type.value,
    )
    session.add(module)
    await session.commit()
    assert module.id is not None
    module_id: int = module.id
    return unit_id, module_id


async def _initial_compute(
    session: AsyncSession,
    entry_id: int,
) -> float:
    """Run the initial emission compute via the service and return total kg_co2eq."""
    entry = (
        await session.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
    ).scalar_one()
    emission_svc = DataEntryEmissionService(session)
    await emission_svc.upsert_by_data_entry(DataEntryResponse.model_validate(entry))
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
    return sum((r.kg_co2eq or 0.0) for r in rows)


async def _read_emissions_on_fresh_engine(
    pg_dsn: str, entry_id: int
) -> list[DataEntryEmission]:
    """Read emissions for an entry on a separate engine.

    Cross-connection visibility check — proves the recalc workflow's
    writes are committed and visible to a different connection pool.
    """
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
            # Detach so callers can inspect attributes after the session closes.
            for r in rows:
                vs.expunge(r)
            return list(rows)
    finally:
        await verify_engine.dispose()


# ── 1. travel / plane — kind_field declared, value derived in pre_compute ──


@pytest.mark.asyncio
async def test_travel_plane_factor_values_change_propagates(pg_dsn):
    """Plane factor: change ``ef_kg_co2eq_per_km`` from 0.1 → 0.2 and run
    the recalc workflow.  Assert the persisted ``kg_co2eq`` doubles.

    Plane is the canonical Strategy-B handler: ``kind_field='category'``
    is declared but ``category`` is derived from ``haul_category`` in
    ``pre_compute``, so the JSON-link bulk-prefetch gate
    (``kind_field in entry.data``) never matches.  The propagation goes
    through the per-entry ``upsert_by_data_entry`` path, which re-runs
    ``pre_compute`` (calling LocationService) and ``_fetch_factors``
    (running the live Strategy B classification query).
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.professional_travel
        )

        # Two airports — short-haul distance (Geneva → Paris ~ 410 km +
        # 95 km approach = ~505 km, in the < 800 km bucket).
        s.add_all(
            [
                Location(
                    transport_mode=TransportModeEnum.plane,
                    name="Geneva",
                    iata_code="GVA",
                    latitude=46.2381,
                    longitude=6.1090,
                    country_code="CH",
                    natural_key=Location.compute_natural_key(
                        transport_mode=TransportModeEnum.plane,
                        iata_code="GVA",
                    ),
                ),
                Location(
                    transport_mode=TransportModeEnum.plane,
                    name="Paris CDG",
                    iata_code="CDG",
                    latitude=49.0097,
                    longitude=2.5479,
                    country_code="FR",
                    natural_key=Location.compute_natural_key(
                        transport_mode=TransportModeEnum.plane,
                        iata_code="CDG",
                    ),
                ),
            ]
        )
        await s.commit()

        factor = Factor(
            emission_type_id=EmissionType.professional_travel__plane.value,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            classification={"category": "very_short_haul"},
            values={"ef_kg_co2eq_per_km": 0.1},
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id: int = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=module_id,
            data={
                "user_institutional_id": "U-001",
                "origin_iata": "GVA",
                "destination_iata": "CDG",
                "cabin_class": "eco",
                "number_of_trips": 1,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        initial_total = await _initial_compute(s, entry_id)
    assert initial_total > 0, "initial compute must produce non-zero kg_co2eq"

    # Bump the EF.
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_km": 0.2}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        stats = await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.plane, 2025)
        await s.commit()
    assert stats["recalculated"] == 1
    assert stats["errors"] == 0, stats["error_details"]

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    await engine.dispose()

    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3), (
        "Doubling ef_kg_co2eq_per_km must double the persisted kg_co2eq. "
        f"initial={initial_total}, new={new_total}"
    )


@pytest.mark.asyncio
async def test_travel_plane_factor_drop_clears_emission(pg_dsn):
    """Plane factor row deleted (no other category covers the entry's
    haul_category) → ``_fetch_factors`` returns ``[]`` → emission rows
    for the entry are deleted on recalc.

    Same strict-drop contract as Strategy A in PR #1027 — minus the
    intermediate "primary_factor_id = None" rewrite, which only applies
    to JSON-link handlers.  For Strategy B, the drop signal *is* the
    classification miss in ``_fetch_factors``.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.professional_travel
        )
        s.add_all(
            [
                Location(
                    transport_mode=TransportModeEnum.plane,
                    name="Geneva",
                    iata_code="GVA",
                    latitude=46.2381,
                    longitude=6.1090,
                    natural_key=Location.compute_natural_key(
                        transport_mode=TransportModeEnum.plane,
                        iata_code="GVA",
                    ),
                ),
                Location(
                    transport_mode=TransportModeEnum.plane,
                    name="Paris CDG",
                    iata_code="CDG",
                    latitude=49.0097,
                    longitude=2.5479,
                    natural_key=Location.compute_natural_key(
                        transport_mode=TransportModeEnum.plane,
                        iata_code="CDG",
                    ),
                ),
            ]
        )
        await s.commit()

        factor = Factor(
            emission_type_id=EmissionType.professional_travel__plane.value,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            classification={"category": "very_short_haul"},
            values={"ef_kg_co2eq_per_km": 0.1},
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id: int = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=module_id,
            data={
                "user_institutional_id": "U-001",
                "origin_iata": "GVA",
                "destination_iata": "CDG",
                "cabin_class": "eco",
                "number_of_trips": 1,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        initial_total = await _initial_compute(s, entry_id)
    assert initial_total > 0

    # Drop the factor — no remaining row matches the haul_category.
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        await s.delete(f)
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.plane, 2025)
        await s.commit()

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    await engine.dispose()
    assert new_rows == [], (
        "Strict-drop contract: when the factor disappears, the data_entry's "
        "emissions are removed (Strategy B path defers to _fetch_factors miss)."
    )


# ── 2. travel / train — kind_field=None, country_code derived in pre_compute ──


@pytest.mark.asyncio
async def test_travel_train_factor_values_change_propagates(pg_dsn):
    """Train factor: change ``ef_kg_co2eq_per_km`` from 0.05 → 0.10 and
    run recalc.  Assert ``kg_co2eq`` doubles.

    Train handler has ``kind_field=None`` (inherited from
    ``ProfessionalTravelBaseModuleHandler``); the factor is keyed by
    ``country_code`` in classification, derived in ``pre_compute`` from
    origin/destination Locations.  Strategy B (B1) classification query
    in ``_fetch_factors`` resolves it.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.professional_travel
        )
        s.add_all(
            [
                Location(
                    transport_mode=TransportModeEnum.train,
                    name="Geneva",
                    latitude=46.2104,
                    longitude=6.1428,
                    country_code="CH",
                    natural_key=Location.compute_natural_key(
                        transport_mode=TransportModeEnum.train,
                        name="Geneva",
                        latitude=46.2104,
                        longitude=6.1428,
                        country_code="CH",
                    ),
                ),
                Location(
                    transport_mode=TransportModeEnum.train,
                    name="Lausanne",
                    latitude=46.5167,
                    longitude=6.6322,
                    country_code="CH",
                    natural_key=Location.compute_natural_key(
                        transport_mode=TransportModeEnum.train,
                        name="Lausanne",
                        latitude=46.5167,
                        longitude=6.6322,
                        country_code="CH",
                    ),
                ),
            ]
        )
        await s.commit()

        factor = Factor(
            emission_type_id=EmissionType.professional_travel__train.value,
            data_entry_type_id=DataEntryTypeEnum.train.value,
            classification={"country_code": "CH"},
            values={"ef_kg_co2eq_per_km": 0.05},
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id: int = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.train.value,
            carbon_report_module_id=module_id,
            data={
                "user_institutional_id": "U-001",
                "origin_name": "Geneva",
                "destination_name": "Lausanne",
                "origin_natural_key": Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Geneva",
                    latitude=46.2104,
                    longitude=6.1428,
                    country_code="CH",
                ),
                "destination_natural_key": Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Lausanne",
                    latitude=46.5167,
                    longitude=6.6322,
                    country_code="CH",
                ),
                "cabin_class": "second",
                "number_of_trips": 1,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        initial_total = await _initial_compute(s, entry_id)
    assert initial_total > 0

    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_km": 0.10}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        stats = await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.train, 2025)
        await s.commit()
    assert stats["errors"] == 0, stats["error_details"]

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    await engine.dispose()

    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


# ── 3. headcount / member — 1:N, kind_field=None ──


@pytest.mark.asyncio
async def test_headcount_member_factor_values_change_propagates(pg_dsn):
    """Member entry produces 3 emission rows (food, waste, commuting),
    one per factor returned by the B3 classification query.  Mutating
    one factor's ``ef_kg_co2eq_per_unit`` must update the matching
    emission row's ``kg_co2eq`` on recalc.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.headcount
        )
        # B3 path of ``_fetch_factors`` walks ``get_subtree_leaves`` of
        # the FactorQuery's emission_type, so factors must be seeded at
        # the leaf level (food → food__vegetarian; commuting → one of
        # commuting__*).  Production seeds use ``_resolve_headcount_factor``
        # to derive the leaf id from headcount_category/class.
        s.add_all(
            [
                Factor(
                    emission_type_id=EmissionType.food__vegetarian.value,
                    data_entry_type_id=DataEntryTypeEnum.member.value,
                    classification={
                        "headcount_category": "food",
                        "headcount_class": "vegetarian",
                    },
                    values={
                        "ef_kg_co2eq_per_unit": 1.0,
                        "number_of_unit_per_fte": 100.0,
                    },
                    year=2025,
                ),
                Factor(
                    emission_type_id=EmissionType.waste__incineration.value,
                    data_entry_type_id=DataEntryTypeEnum.member.value,
                    classification={
                        "headcount_category": "waste",
                        "headcount_class": "incineration",
                    },
                    values={
                        "ef_kg_co2eq_per_unit": 0.5,
                        "number_of_unit_per_fte": 50.0,
                    },
                    year=2025,
                ),
                Factor(
                    emission_type_id=EmissionType.commuting__public_transport.value,
                    data_entry_type_id=DataEntryTypeEnum.member.value,
                    classification={
                        "headcount_category": "commuting",
                        "headcount_class": "public_transport",
                    },
                    values={
                        "ef_kg_co2eq_per_unit": 0.2,
                        "number_of_unit_per_fte": 200.0,
                    },
                    year=2025,
                ),
            ]
        )
        await s.commit()

        food_factor_id_q = await s.execute(
            select(Factor).where(
                col(Factor.emission_type_id) == EmissionType.food__vegetarian.value
            )
        )
        food_factor: Factor = food_factor_id_q.scalar_one()

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=module_id,
            data={
                "name": "Alice",
                "user_institutional_id": "M-001",
                "fte": 1.0,
                "sius_code": "51",
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id
        assert food_factor.id is not None
        food_factor_id: int = food_factor.id

    async with Sf() as s:
        await _initial_compute(s, entry_id)

    initial_food_kg: float | None = None
    initial_other_kg: float = 0.0
    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id) == entry_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            if r.emission_type_id == EmissionType.food__vegetarian.value:
                initial_food_kg = r.kg_co2eq
            elif r.emission_type_id != EmissionType.headcount.value:
                # Skip rollup row.
                initial_other_kg += r.kg_co2eq or 0.0
    if initial_food_kg is None:
        raise AssertionError("food emission row not produced on initial compute")

    # Double the food factor's EF only.
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == food_factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_unit": 2.0}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.member, 2025)
        await s.commit()

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    new_food_kg: float | None = None
    new_other_kg: float = 0.0
    for r in new_rows:
        if r.emission_type_id == EmissionType.food__vegetarian.value:
            new_food_kg = r.kg_co2eq
        elif r.emission_type_id != EmissionType.headcount.value:
            new_other_kg += r.kg_co2eq or 0.0
    await engine.dispose()

    if new_food_kg is None:
        raise AssertionError("food row missing after recalc")
    assert new_food_kg == pytest.approx(initial_food_kg * 2.0, rel=1e-3), (
        f"food kg_co2eq should double; initial={initial_food_kg}, new={new_food_kg}"
    )
    assert new_other_kg == pytest.approx(initial_other_kg, rel=1e-3), (
        "non-food emissions must remain unchanged when only the food factor mutates"
    )


# ── 4. headcount / student — 1:N, kind_field=None ──


@pytest.mark.asyncio
async def test_headcount_student_factor_values_change_propagates(pg_dsn):
    """Student entry mirrors member but on ``DataEntryTypeEnum.student``.
    Same Strategy B (B3) classification path.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.headcount
        )
        s.add_all(
            [
                Factor(
                    emission_type_id=EmissionType.food__vegetarian.value,
                    data_entry_type_id=DataEntryTypeEnum.student.value,
                    classification={
                        "headcount_category": "food",
                        "headcount_class": "vegetarian",
                    },
                    values={
                        "ef_kg_co2eq_per_unit": 1.0,
                        "number_of_unit_per_fte": 100.0,
                    },
                    year=2025,
                ),
                Factor(
                    emission_type_id=EmissionType.waste__incineration.value,
                    data_entry_type_id=DataEntryTypeEnum.student.value,
                    classification={
                        "headcount_category": "waste",
                        "headcount_class": "incineration",
                    },
                    values={
                        "ef_kg_co2eq_per_unit": 0.5,
                        "number_of_unit_per_fte": 50.0,
                    },
                    year=2025,
                ),
                Factor(
                    emission_type_id=EmissionType.commuting__public_transport.value,
                    data_entry_type_id=DataEntryTypeEnum.student.value,
                    classification={
                        "headcount_category": "commuting",
                        "headcount_class": "public_transport",
                    },
                    values={
                        "ef_kg_co2eq_per_unit": 0.2,
                        "number_of_unit_per_fte": 200.0,
                    },
                    year=2025,
                ),
            ]
        )
        await s.commit()

        food_factor: Factor = (
            await s.execute(
                select(Factor).where(
                    col(Factor.data_entry_type_id) == DataEntryTypeEnum.student.value,
                    col(Factor.emission_type_id) == EmissionType.food__vegetarian.value,
                )
            )
        ).scalar_one()
        assert food_factor.id is not None
        food_factor_id: int = food_factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.student.value,
            carbon_report_module_id=module_id,
            data={"fte": 1.0},
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        initial_total = await _initial_compute(s, entry_id)
    assert initial_total > 0

    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == food_factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_unit": 2.0}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.student, 2025)
        await s.commit()

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    new_food_kg: float | None = None
    for r in new_rows:
        if r.emission_type_id == EmissionType.food__vegetarian.value:
            new_food_kg = r.kg_co2eq
    await engine.dispose()
    if new_food_kg is None:
        raise AssertionError("food row missing after student recalc")
    # Initial food kg = fte (1.0) * number_of_unit_per_fte (100) * ef (1.0) = 100
    # New food kg     = fte (1.0) * number_of_unit_per_fte (100) * ef (2.0) = 200
    assert new_food_kg == pytest.approx(200.0, rel=1e-3)


# ── 5. building_embodied_energy — kind_field=None, B1 classification query ──


@pytest.mark.asyncio
async def test_building_embodied_energy_factor_values_change_propagates(pg_dsn):
    """Embodied energy factor: change ``ef_kgco2eq_per_m2`` from 100 →
    200.  ``kg_co2eq = surface_m2 × ef``, so the emission must double.

    Handler has ``kind_field=None`` and runs a ``FactorQuery`` keyed on
    ``building_name`` in classification (B1 path with fallback).  The
    surface is baked into ``entry.data['room_surface_square_meter']`` by
    the upstream ``EmbodiedEnergyWorkflow.post_create`` step; the handler
    has no ``pre_compute``, so that field must be present on the entry.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.buildings
        )

        factor = Factor(
            emission_type_id=EmissionType.buildings__embodied_energy.value,
            data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
            classification={"building_name": "BC", "category": "default"},
            values={"ef_kgco2eq_per_m2": 100.0},
            year=2025,
        )
        s.add(factor)
        await s.commit()
        assert factor.id is not None
        factor_id: int = factor.id

        # ``EmbodiedEnergyWorkflow._make_building_embodied_energy_data``
        # bakes ``room_surface_square_meter`` directly into entry.data —
        # the handler has no pre_compute, so this is the only source.
        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.building_embodied_energy.value,
            carbon_report_module_id=module_id,
            data={"building_name": "BC", "room_surface_square_meter": 50.0},
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        initial_total = await _initial_compute(s, entry_id)
    assert initial_total == pytest.approx(50.0 * 100.0, rel=1e-3), (
        f"initial embodied = surface (50) × ef (100) = 5000; got {initial_total}"
    )

    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kgco2eq_per_m2": 200.0}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        await wf.recalculate_for_data_entry_type(
            DataEntryTypeEnum.building_embodied_energy, 2025
        )
        await s.commit()

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    await engine.dispose()
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


# ── 6. building_room (1:N) — kind_field='building_name' (JSON-link, regression) ──


@pytest.mark.asyncio
async def test_building_room_factor_values_change_propagates_all_5_emissions(
    pg_dsn,
):
    """Building room is technically JSON-link (``kind_field='building_name'``
    is on entry.data) but emits 5 leaf emissions per entry (one per
    energy type: lighting, cooling, ventilation, heating_elec,
    heating_thermal).  This regression net asserts that doubling
    ``ef_kg_co2eq_per_kwh`` doubles **every** kg_co2eq leaf and that the
    rollup row sums correctly.

    The plan doc originally classified rooms as Strategy B; in fact the
    Strategy A bulk-prefetch covers it, because both ``kind_field`` and
    ``subkind_field`` ('room_type') are on entry.data.
    """
    from app.models.building_room import BuildingRoom

    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, module_id = await _seed_unit_and_module(
            s, module_type=ModuleTypeEnum.buildings
        )
        room = BuildingRoom(
            building_location="EPFL",
            building_name="BC",
            room_name="BC-150",
            room_type="office",
            room_surface_square_meter=10.0,
        )
        s.add(room)
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
        factor_id: int = factor.id

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
        await _initial_compute(s, entry_id)

    async with Sf() as s:
        initial_rows = (
            (
                await s.execute(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id) == entry_id
                    )
                )
            )
            .scalars()
            .all()
        )
        initial_per_leaf: dict[int, float] = {
            r.emission_type_id: (r.kg_co2eq or 0.0)
            for r in initial_rows
            if r.emission_type_id != EmissionType.buildings__rooms.value
        }
    assert len(initial_per_leaf) >= 4, (
        "building room must produce at least 4 leaf emission rows "
        "(lighting + cooling + ventilation + heating). "
        f"got {len(initial_per_leaf)}: {sorted(initial_per_leaf)}"
    )

    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_kwh": 0.2}
        await s.commit()

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.building, 2025)
        await s.commit()

    new_rows = await _read_emissions_on_fresh_engine(pg_dsn, entry_id)
    new_per_leaf: dict[int, float] = {
        r.emission_type_id: (r.kg_co2eq or 0.0)
        for r in new_rows
        if r.emission_type_id != EmissionType.buildings__rooms.value
    }
    await engine.dispose()
    assert set(new_per_leaf.keys()) == set(initial_per_leaf.keys()), (
        "the same set of leaf emission rows must remain after recalc"
    )
    for et_id, initial_kg in initial_per_leaf.items():
        assert new_per_leaf[et_id] == pytest.approx(initial_kg * 2.0, rel=1e-3), (
            f"leaf emission_type_id={et_id} must double; "
            f"initial={initial_kg}, new={new_per_leaf[et_id]}"
        )
