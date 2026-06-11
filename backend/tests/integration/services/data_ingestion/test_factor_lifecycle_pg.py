"""Plan 310 test-coverage Unit 7/11 — factor lifecycle pin.

Pins behaviour for the three factor lifecycle events:

- **insert** — a new factor row appears in the DB and previously-unmatched
  ``DataEntry`` rows for the same ``(data_entry_type_id, year)`` pick it
  up on the next recalc.  Two variants:

  * Strategy A (JSON-link): equipment.  The handler exposes a
    ``kind_field`` (``equipment_class``) AND every entry carries that
    key in ``entry.data``, so the bulk-prefetch branch in
    ``EmissionRecalculationWorkflow`` rewrites
    ``entry.data['primary_factor_id']`` in-place.
  * Strategy B (FK-link): travel/plane.  The handler declares
    ``kind_field='category'`` but derives ``category`` in
    ``pre_compute``, so the JSON-link gate misses; the live B1
    classification query inside ``_fetch_factors`` resolves the freshly
    inserted factor.

- **upsert** — an existing factor's ``values`` change.  Codified as the
  load-bearing regression gate for Plan 310-B's auto-recalc: the
  emission's ``kg_co2eq`` must reflect the new value after recalc.

- **delete via reupload (discovery)** — factors.csv #2 reuploaded WITHOUT
  factor F.  This file pins what the system *actually does* today, so
  future Tier-N work can build on the observed contract:

  * ``factor_repo.upsert_factors`` only ever inserts-or-updates and
    stamps ``last_seen_job_id``.  It NEVER deletes rows that are absent
    from the new batch — that would re-introduce the dangling-FK class
    of bugs the JSON-link path (``DataEntry.data['primary_factor_id']``)
    is exactly designed to dodge.
  * Effect: the dropped factor row is *kept-stale* — same id,
    ``last_seen_job_id`` still points at the OLD job (so
    ``list_stale_for_year`` flags it for operator action), and dependent
    ``data_entry_emissions`` are NOT cleared by the next recalc because
    the in-DB factor still resolves the rematch.
  * Stale-cleanup is therefore a deliberate operator action (the
    ``/factors/stale`` endpoint), not an automatic side-effect of the
    next CSV reupload.

If a future change shifts the behaviour (e.g. a "purge missing factors"
admin path, a cascade-delete on ``Factor.id`` going through
``ON DELETE SET NULL``, …), THIS test will start failing — and that is
on purpose.  Update the assertions and the contract docstring above
together so the deliberate change is reviewable.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import UserProvider
from app.repositories.factor_repo import FactorRepository
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

# ── Helpers ────────────────────────────────────────────────────────────


async def _seed_unit_and_module(
    session: AsyncSession,
    *,
    module_type: ModuleTypeEnum,
    year: int = 2025,
) -> int:
    """Seed Unit + CarbonReport + CarbonReportModule, returning the module id."""
    unit = Unit(
        institutional_code="TEST",
        institutional_id="TEST-UNIT",
        name="Test Unit",
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
    return module.id


def _seed_factor_job(
    *,
    module_type_id: int,
    data_entry_type_id: int | None,
    year: int = 2025,
    is_current: bool = True,
) -> DataIngestionJob:
    """Mirrors a finished is_current FACTORS CSV job — referenced by
    ``last_seen_job_id`` on the upserted factor rows."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=year,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=is_current,
    )


@asynccontextmanager
async def _fresh_session(pg_dsn: str) -> AsyncIterator[AsyncSession]:
    """Yield an ``AsyncSession`` on a one-shot engine bound to ``pg_dsn``.

    Cross-connection read pattern — used by the verification blocks
    after each test's writer engine is disposed, to prove writes are
    committed and visible to a different connection pool.  Caller is
    responsible for ``expunge`` on any rows it wants to inspect after
    the session closes.
    """
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            yield vs
    finally:
        await verify_engine.dispose()


async def _emissions_for_entry(
    session: AsyncSession, entry_id: int
) -> list[DataEntryEmission]:
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


# ── 1. Insert (Strategy A — equipment, JSON-link path) ─────────────────


@pytest.mark.asyncio
async def test_new_factor_matches_unmatched_entries_strategy_a(
    pg_dsn,
):
    """Strategy A (JSON-link): a DataEntry with ``primary_factor_id=None``
    whose ``equipment_class`` matches a factor introduced by a fresh
    ``upsert_factors`` call must pick that factor up on the next recalc
    and produce a non-zero emission.

    Mirrors the CSV reupload scenario: factors.csv has a new
    ``Laptop / Standard`` row that wasn't in the DB before; existing
    DataEntries that referenced ``Laptop / Standard`` were stranded with
    ``primary_factor_id=None`` and no emission rows.  The recalc
    workflow's bulk-prefetch path rewrites ``entry.data['primary_factor_id']``
    to the new factor's id and ``upsert_by_data_entry`` produces fresh
    emissions.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.equipment_electric_consumption
            )

            # FACTORS job that ``upsert_factors`` will stamp on
            # ``last_seen_job_id``.  ``data_entry_type_id`` pinned to ``it``
            # so the row is shaped like a single-type factor upload.
            job = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
            )
            s.add(job)
            await s.commit()
            assert job.id is not None
            job_id: int = job.id

            # DataEntry seeded WITHOUT a matching factor in the DB —
            # primary_factor_id starts as None (the un-rematched state a
            # CSV ingest of data with no covering factor leaves behind).
            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.it.value,
                carbon_report_module_id=module_id,
                data={
                    "primary_factor_id": None,
                    "equipment_class": "Laptop",
                    "sub_class": "Standard",
                    "active_usage_hours_per_week": 40.0,
                    "standby_usage_hours_per_week": 128.0,
                    "name": "Test Laptop",
                },
            )
            s.add(entry)
            await s.commit()
            assert entry.id is not None
            entry_id: int = entry.id

        # No emissions yet — confirm the unmatched starting state.
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
            assert initial_rows == [], (
                "Pre-condition: entry should have no emissions before factor insert"
            )

        # Insert the factor via the production upsert path — same call
        # ``BaseFactorCSVProvider._upsert_batch`` makes per CSV batch.
        async with Sf() as s:
            new_factor = Factor(
                emission_type_id=EmissionType.equipment__it.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                classification={
                    "equipment_class": "Laptop",
                    "sub_class": "Standard",
                },
                values={
                    "active_power_w": 100.0,
                    "standby_power_w": 10.0,
                    "ef_kg_co2eq_per_kwh": 0.1,
                },
                year=2025,
            )
            repo = FactorRepository(s)
            affected = await repo.upsert_factors([new_factor], current_job_id=job_id)
            await s.commit()
            assert affected == 1, "fresh factor row should insert"

        # Trigger the recalc the way ``factor_ingest`` would on success.
        async with Sf() as s:
            wf = EmissionRecalculationWorkflow(s)
            stats = await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)
            await s.commit()
        assert stats["recalculated"] == 1, stats
        assert stats["errors"] == 0, stats["error_details"]
    finally:
        await engine.dispose()

    # Verify on a fresh engine — entry's primary_factor_id rewritten,
    # emissions present and non-zero.
    async with _fresh_session(pg_dsn) as vs:
        refreshed_entry = (
            await vs.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        new_rows = await _emissions_for_entry(vs, entry_id)
    assert refreshed_entry.data.get("primary_factor_id") is not None, (
        "Strategy A rematch must populate primary_factor_id from factor_lookup"
    )
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    assert new_total > 0, (
        "Inserting the matching factor must produce a non-zero emission "
        f"on recalc; got rows={new_rows}"
    )


# ── 2. Insert (Strategy B — travel/plane, FK-link path) ────────────────


@pytest.mark.asyncio
async def test_new_factor_matches_unmatched_entries_strategy_b(
    pg_dsn,
):
    """Strategy B (FK-link): a plane DataEntry seeded BEFORE the matching
    factor exists must produce a non-zero emission once a fresh
    ``upsert_factors`` introduces the factor and the recalc runs.

    Plane is the canonical Strategy B handler: ``kind_field='category'``
    is declared but ``category`` is derived from ``haul_category`` in
    ``pre_compute``, so ``category`` is NOT in ``entry.data`` and the
    JSON-link bulk-prefetch gate misses.  Resolution goes through
    ``_fetch_factors``'s live B1 classification query, which only
    succeeds once the factor row lands.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.professional_travel
            )

            # Two airports — short-haul distance keeps the entry inside
            # the ``very_short_haul`` bucket the factor below classifies.
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

            job = _seed_factor_job(
                module_type_id=ModuleTypeEnum.professional_travel.value,
                data_entry_type_id=DataEntryTypeEnum.plane.value,
            )
            s.add(job)
            await s.commit()
            assert job.id is not None
            job_id: int = job.id

            # Entry seeded BEFORE the factor — the very-short-haul plane
            # factor doesn't yet exist, so initial compute would produce
            # nothing.  No primary_factor_id on the entry: Strategy B
            # never writes one.
            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                carbon_report_module_id=module_id,
                data={
                    "user_institutional_id": "U-001",
                    "origin_iata": "GVA",
                    "destination_iata": "CDG",
                    "cabin_class": "economy",
                    "number_of_trips": 1,
                },
            )
            s.add(entry)
            await s.commit()
            assert entry.id is not None
            entry_id: int = entry.id

        # No factor → no emissions yet.
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
            assert initial_rows == [], (
                "Pre-condition: plane entry should have no emissions before "
                "the factor is upserted"
            )

        # Insert the factor.
        async with Sf() as s:
            new_factor = Factor(
                emission_type_id=EmissionType.professional_travel__plane.value,
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                classification={
                    "category": "very_short_haul",
                    "cabin_class": "economy",
                },
                values={
                    "ef_kg_co2eq_per_km": 0.1,
                    "min_distance": 0,
                    "max_distance": 800,
                },
                year=2025,
            )
            repo = FactorRepository(s)
            affected = await repo.upsert_factors([new_factor], current_job_id=job_id)
            await s.commit()
            assert affected == 1

        # Trigger the recalc.
        async with Sf() as s:
            wf = EmissionRecalculationWorkflow(s)
            stats = await wf.recalculate_for_data_entry_type(
                DataEntryTypeEnum.plane, 2025
            )
            await s.commit()
        assert stats["recalculated"] == 1, stats
        assert stats["errors"] == 0, stats["error_details"]
    finally:
        await engine.dispose()

    # Verify cross-connection — emissions present, non-zero.
    async with _fresh_session(pg_dsn) as vs:
        new_rows = await _emissions_for_entry(vs, entry_id)
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    assert new_total > 0, (
        "Strategy B: introducing the matching factor and recalculating must "
        f"produce a non-zero plane emission; got rows={new_rows}"
    )


# ── 3. Upsert (existing factor's values change) ────────────────────────


@pytest.mark.asyncio
async def test_factor_upsert_triggers_recompute(pg_dsn):
    """Existing factor's ``values`` change → ``upsert_factors`` updates
    the row in place (preserving ``id`` and any ``DataEntry.primary_factor_id``
    references) → recalc reflects the new value.

    This is the load-bearing regression gate for Plan 310-B's auto-recalc:
    if a future change ever stops upsert from updating in place (e.g. a
    delete-and-insert variant that breaks the FK), this test fails.

    Doubling ``ef_kg_co2eq_per_kwh`` doubles the persisted ``kg_co2eq``.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.equipment_electric_consumption
            )

            # First factor job — original values.
            job_v1 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                is_current=False,
            )
            s.add(job_v1)
            await s.commit()
            assert job_v1.id is not None
            job_v1_id: int = job_v1.id

            repo = FactorRepository(s)
            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "Standard",
                        },
                        values={
                            "active_power_w": 100.0,
                            "standby_power_w": 10.0,
                            "ef_kg_co2eq_per_kwh": 0.1,
                        },
                        year=2025,
                    )
                ],
                current_job_id=job_v1_id,
            )
            await s.commit()

            # Now resolve the freshly-inserted factor's id so we can pin
            # primary_factor_id on the data entry below.
            initial_factor: Factor = (
                await s.execute(
                    select(Factor).where(
                        col(Factor.data_entry_type_id) == DataEntryTypeEnum.it.value,
                        col(Factor.year) == 2025,
                    )
                )
            ).scalar_one()
            assert initial_factor.id is not None
            factor_id: int = initial_factor.id

            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.it.value,
                carbon_report_module_id=module_id,
                data={
                    "primary_factor_id": factor_id,
                    "equipment_class": "Laptop",
                    "sub_class": "Standard",
                    "active_usage_hours_per_week": 40.0,
                    "standby_usage_hours_per_week": 128.0,
                    "name": "Test Laptop",
                },
            )
            s.add(entry)
            await s.commit()
            assert entry.id is not None
            entry_id: int = entry.id

        # Initial compute against factor v1.
        async with Sf() as s:
            e = (
                await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
            ).scalar_one()
            await DataEntryEmissionService(s).upsert_by_data_entry(
                DataEntryResponse.model_validate(e)
            )
            await s.commit()

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
        initial_total = sum((r.kg_co2eq or 0.0) for r in initial_rows)
        assert initial_total > 0

        # Reupload — same identity, doubled EF.  Second is_current job.
        async with Sf() as s:
            job_v2 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                is_current=True,
            )
            s.add(job_v2)
            await s.commit()
            assert job_v2.id is not None
            job_v2_id: int = job_v2.id

            repo = FactorRepository(s)
            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "Standard",
                        },
                        values={
                            "active_power_w": 100.0,
                            "standby_power_w": 10.0,
                            "ef_kg_co2eq_per_kwh": 0.2,  # doubled
                        },
                        year=2025,
                    )
                ],
                current_job_id=job_v2_id,
            )
            await s.commit()
            s.expire_all()

            # Identity preservation — same id, new last_seen_job_id.
            updated: Factor = (
                await s.execute(select(Factor).where(col(Factor.id) == factor_id))
            ).scalar_one()
            assert updated.values["ef_kg_co2eq_per_kwh"] == 0.2
            assert updated.last_seen_job_id == job_v2_id, (
                "upsert must stamp the new job id"
            )

        # Auto-recalc.
        async with Sf() as s:
            wf = EmissionRecalculationWorkflow(s)
            stats = await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)
            await s.commit()
        assert stats["errors"] == 0, stats["error_details"]
    finally:
        await engine.dispose()

    async with _fresh_session(pg_dsn) as vs:
        new_rows = await _emissions_for_entry(vs, entry_id)
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3), (
        "Plan 310-B regression gate: doubling the factor's EF must double "
        f"the persisted kg_co2eq.  initial={initial_total}, new={new_total}"
    )


# ── 4. Delete via reupload — discovery test ────────────────────────────


@pytest.mark.asyncio
async def test_factor_delete_via_reupload_observes_actual_behaviour(
    pg_dsn,
):
    """Discovery test — pin the actual (kept-stale) contract for a CSV
    reupload that omits a factor.

    Setup
    -----
    1. factors.csv #1 has factor F (Laptop / Standard), upserted by
       job_v1 (FACTORS, is_current=False after step 2).
    2. DataEntry seeded with ``primary_factor_id=F.id``; initial compute
       produces non-zero emissions.
    3. factors.csv #2 is uploaded as job_v2 (FACTORS, is_current=True)
       and contains a DIFFERENT factor (Tablet / Standard) — F is missing.
    4. Recalc runs (auto-trigger after factor_ingest).

    What the system actually does today (the *contract* this test pins):

    - ``factors.F`` is **NOT deleted**.  Its row is kept with the OLD
      ``last_seen_job_id`` (= job_v1_id).  A naive "upsert deletes
      missing rows" reading of the CSV reupload would clear F; the
      production upsert path explicitly does not, to avoid dangling FKs
      against ``DataEntry.data['primary_factor_id']``.
    - ``list_stale_for_year(2025)`` flags F (its
      ``last_seen_job_id < latest_id`` for the (det, year) — exactly
      the operator-facing signal Plan 310-B's stale endpoint is
      designed to surface).
    - The ``DataEntry``'s ``primary_factor_id`` is preserved (still
      points at F).  Strategy A's bulk-prefetch rematch reads from
      ``factor_repo.list_by_data_entry_type`` (not "factors written by
      the latest job"), so F is still in ``factor_lookup`` and the
      rematch leaves the link alone.
    - ``data_entry_emissions`` rows are kept and recomputed against F's
      OLD values — they are NOT cleared and NOT NULLed.

    So a CSV reupload that omits a factor is a soft-deprecation: the
    factor goes stale-but-functional, dependent emissions stay valid
    against the old EF, and only the operator's explicit cleanup via
    ``/factors/stale`` (or a manual Factor DELETE) actually removes the
    row.

    If a future change shifts this — e.g. cascade-delete on missing
    factors, NULL-out of dependent ``primary_factor_id``, eager
    recomputation of emissions — these assertions will start failing
    and the contract docstring above must be updated alongside the
    code change.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.equipment_electric_consumption
            )

            # ── factors.csv #1 — F (Laptop / Standard) ─────────────────
            job_v1 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                is_current=False,  # demoted by the v2 upload below
            )
            s.add(job_v1)
            await s.commit()
            assert job_v1.id is not None
            job_v1_id: int = job_v1.id

            repo = FactorRepository(s)
            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "Standard",
                        },
                        values={
                            "active_power_w": 100.0,
                            "standby_power_w": 10.0,
                            "ef_kg_co2eq_per_kwh": 0.1,
                        },
                        year=2025,
                    )
                ],
                current_job_id=job_v1_id,
            )
            await s.commit()

            factor_F: Factor = (
                await s.execute(
                    select(Factor).where(
                        col(Factor.data_entry_type_id) == DataEntryTypeEnum.it.value,
                        col(Factor.year) == 2025,
                    )
                )
            ).scalar_one()
            assert factor_F.id is not None
            factor_F_id: int = factor_F.id
            assert factor_F.last_seen_job_id == job_v1_id

            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.it.value,
                carbon_report_module_id=module_id,
                data={
                    "primary_factor_id": factor_F_id,
                    "equipment_class": "Laptop",
                    "sub_class": "Standard",
                    "active_usage_hours_per_week": 40.0,
                    "standby_usage_hours_per_week": 128.0,
                    "name": "Test Laptop",
                },
            )
            s.add(entry)
            await s.commit()
            assert entry.id is not None
            entry_id: int = entry.id

        # Initial compute against F.
        async with Sf() as s:
            e = (
                await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
            ).scalar_one()
            await DataEntryEmissionService(s).upsert_by_data_entry(
                DataEntryResponse.model_validate(e)
            )
            await s.commit()

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
        initial_total = sum((r.kg_co2eq or 0.0) for r in initial_rows)
        assert initial_total > 0, (
            "Pre-condition: initial compute against factor F must produce "
            "non-zero emissions"
        )

        # ── factors.csv #2 — F MISSING, only Tablet/Standard ───────────
        async with Sf() as s:
            job_v2 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                is_current=True,
            )
            s.add(job_v2)
            await s.commit()
            assert job_v2.id is not None
            job_v2_id: int = job_v2.id

            repo = FactorRepository(s)
            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Tablet",
                            "sub_class": "Standard",
                        },
                        values={
                            "active_power_w": 5.0,
                            "standby_power_w": 1.0,
                            "ef_kg_co2eq_per_kwh": 0.2,
                        },
                        year=2025,
                    )
                ],
                current_job_id=job_v2_id,
            )
            await s.commit()

        # Auto-recalc — what factor_ingest_handler chains on success.
        async with Sf() as s:
            wf = EmissionRecalculationWorkflow(s)
            stats = await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)
            await s.commit()
        assert stats["errors"] == 0, stats["error_details"]
    finally:
        await engine.dispose()

    # ── Observed behaviour assertions — pin the contract ────────────────
    async with _fresh_session(pg_dsn) as vs:
        persisted_F = (
            await vs.execute(select(Factor).where(col(Factor.id) == factor_F_id))
        ).scalar_one_or_none()
        stale = await FactorRepository(vs).list_stale_for_year(2025)
        stale_ids = {f.id for f in stale}
        refreshed_entry = (
            await vs.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        new_rows = await _emissions_for_entry(vs, entry_id)

    # 1. F is NOT deleted — upsert path never deletes rows missing from
    #    the new batch.
    assert persisted_F is not None, (
        "Contract: factors.csv reupload omitting F must NOT delete the F "
        "row (avoids dangling FKs in DataEntry.data['primary_factor_id'])."
    )
    assert persisted_F.last_seen_job_id == job_v1_id, (
        "Contract: omitted-from-reupload factor keeps its OLD "
        f"last_seen_job_id (= {job_v1_id}); got {persisted_F.last_seen_job_id}.  "
        "This is what makes ``list_stale_for_year`` flag it."
    )

    # 2. F is surfaced as stale to operators.
    assert factor_F_id in stale_ids, (
        f"Contract: F (id={factor_F_id}) must appear in list_stale_for_year(2025) "
        f"after the reupload omits it; got stale_ids={stale_ids}"
    )

    # 3. The DataEntry's ``primary_factor_id`` is preserved (NOT NULLed).
    assert refreshed_entry.data.get("primary_factor_id") == factor_F_id, (
        "Contract: DataEntry.data['primary_factor_id'] must still point at F "
        "after the reupload — the bulk-prefetch reads from "
        "``factor_repo.list_by_data_entry_type`` which still includes F (it's "
        "in DB, just stale), so the rematch leaves the link alone.  "
        f"Expected={factor_F_id}, got={refreshed_entry.data.get('primary_factor_id')}"
    )

    # 4. Emissions are kept and recomputed against F's OLD values — not
    #    cleared, not NULLed, not silently halved/doubled.
    assert new_rows != [], (
        "Contract: emissions must NOT be cleared just because F was missing "
        "from the CSV reupload.  F is still in DB and still resolves the "
        "rematch."
    )
    new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    assert new_total == pytest.approx(initial_total, rel=1e-3), (
        "Contract: emissions stay computed against F's old values (kept-stale).  "
        f"initial={initial_total}, new={new_total}.  If these diverge, the "
        "system has stopped honouring kept-stale semantics — revisit the "
        "contract docstring."
    )
