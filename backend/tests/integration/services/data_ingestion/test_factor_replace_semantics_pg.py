"""Task 9 (#1661 Phase 2) — ``FactorRepository.delete_stale_for_year``.

Phase 1 removed ``primary_factor_id`` from ``DataEntry.data`` — nothing
resolves a factor id out of an entry payload any more, so a stale
factor row (superseded by a newer CSV upload) is finally safe to
DELETE instead of merely flagged.  ``DataEntryEmission.primary_factor_id``
is the only remaining reference and its FK is ``ondelete="CASCADE"``,
so deleting a stale factor cascades any emission rows still pointing
at it (rebuilt later by the enqueued recalc — Task 10's job).

This test seeds two ingest generations for one ``(det, year)`` exactly
like ``test_factor_lifecycle_pg.py``'s discovery test (same helpers,
same is_current/job mechanics), but instead of pinning the kept-stale
list-only contract it drives the new deletion path and asserts:

- a row dropped entirely from the reupload is deleted;
- a row whose classification changed (so the reupload's UPSERT target
  a different, freshly-inserted row) has its OLD shape deleted;
- rows unchanged across generations, and the new shape of a reshaped
  row, keep their ids;
- an emission row pointing at a doomed factor is cascade-deleted;
- a different ``data_entry_type_id`` (single generation, not stale)
  and a different year (its own stale row) are left untouched by the
  call.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import UserProvider
from app.modules.emissions import EmissionType
from app.repositories.factor_repo import FactorRepository
from app.services.factor_service import FactorService

# ── Helpers (mirrors test_factor_lifecycle_pg.py) ──────────────────────


async def _seed_unit_and_module(
    session: AsyncSession,
    *,
    module_type: ModuleTypeEnum,
    year: int,
) -> int:
    """Seed Unit + CarbonReport + CarbonReportModule, returning the module id."""
    unit = Unit(
        institutional_code=f"TEST-{module_type.name}-{year}",
        institutional_id=f"TEST-UNIT-{module_type.name}-{year}",
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
    year: int,
    is_current: bool,
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

    Used for the post-assertion reads, on a different connection than
    the writer engine, to prove the delete + cascade are committed.
    """
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            yield vs
    finally:
        await verify_engine.dispose()


async def _factor_by_classification(
    session: AsyncSession,
    *,
    data_entry_type_id: int,
    year: int,
    classification: dict,
) -> Factor:
    """Look up the single factor matching classification within (det, year).

    ``upsert_factors`` writes via a COPY/staging path and never backfills
    ``id`` onto the passed-in instance, so tests resolve the persisted
    row by its identity fields instead.
    """
    rows = (
        (
            await session.execute(
                select(Factor).where(
                    col(Factor.data_entry_type_id) == data_entry_type_id,
                    col(Factor.year) == year,
                )
            )
        )
        .scalars()
        .all()
    )
    matches = [f for f in rows if f.classification == classification]
    assert len(matches) == 1, (
        f"expected exactly one factor with classification={classification}; "
        f"got {[f.classification for f in rows]}"
    )
    return matches[0]


@pytest.mark.asyncio
async def test_delete_stale_for_year_removes_superseded_rows_and_cascades(
    pg_dsn,
):
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.equipment, year=2025
            )
            repo = FactorRepository(s)

            # ── Generation 1 (job1, superseded below) ──────────────────
            job1 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                is_current=False,
            )
            s.add(job1)
            await s.commit()
            assert job1.id is not None
            job1_id: int = job1.id

            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "Standard",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.1},
                        year=2025,
                    ),
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Desktop",
                            "sub_class": "Standard",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.2},
                        year=2025,
                    ),
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Tablet",
                            "sub_class": "Standard",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.3},
                        year=2025,
                    ),
                ],
                current_job_id=job1_id,
            )
            await s.commit()

            f_keep_v1 = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                classification={"equipment_class": "Laptop", "sub_class": "Standard"},
            )
            f_drop = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                classification={"equipment_class": "Desktop", "sub_class": "Standard"},
            )
            f_reshape_old = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                classification={"equipment_class": "Tablet", "sub_class": "Standard"},
            )
            assert f_keep_v1.id is not None
            assert f_drop.id is not None
            assert f_reshape_old.id is not None
            keep_id: int = f_keep_v1.id
            drop_id: int = f_drop.id
            reshape_old_id: int = f_reshape_old.id

            # Seed an emission row pointing at the doomed f_drop factor —
            # verifies the FK's ondelete=CASCADE fires once
            # delete_stale_for_year deletes the row it references.
            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.it.value,
                carbon_report_module_id=module_id,
                data={"name": "Doomed entry"},
            )
            s.add(entry)
            await s.commit()
            assert entry.id is not None
            entry_id: int = entry.id

            emission = DataEntryEmission(
                data_entry_id=entry_id,
                emission_type_id=EmissionType.equipment__it.value,
                primary_factor_id=drop_id,
                kg_co2eq=1.23,
            )
            s.add(emission)
            await s.commit()
            assert emission.id is not None
            emission_id: int = emission.id

            # ── Generation 2 (job2, is_current) — Desktop dropped,
            #    Tablet reshaped (sub_class changes → new row), Laptop
            #    unchanged. ────────────────────────────────────────────
            job2 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                is_current=True,
            )
            s.add(job2)
            await s.commit()
            assert job2.id is not None
            job2_id: int = job2.id

            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "Standard",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.1},
                        year=2025,
                    ),
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Tablet",
                            "sub_class": "Pro",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.35},
                        year=2025,
                    ),
                ],
                current_job_id=job2_id,
            )
            await s.commit()

            f_keep_v2 = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                classification={"equipment_class": "Laptop", "sub_class": "Standard"},
            )
            assert f_keep_v2.id == keep_id, (
                "reupload with an unchanged classification must UPDATE the "
                "existing row in place, not insert a new one"
            )

            f_reshape_new = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                classification={"equipment_class": "Tablet", "sub_class": "Pro"},
            )
            assert f_reshape_new.id is not None
            reshape_new_id: int = f_reshape_new.id

            # ── Control: a different det (plane), single generation,
            #    is_current, NOT stale — must survive the sweep. ────────
            await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.professional_travel, year=2025
            )
            job_plane = _seed_factor_job(
                module_type_id=ModuleTypeEnum.professional_travel.value,
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                year=2025,
                is_current=True,
            )
            s.add(job_plane)
            await s.commit()
            assert job_plane.id is not None
            job_plane_id: int = job_plane.id

            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.professional_travel__plane.value,
                        data_entry_type_id=DataEntryTypeEnum.plane.value,
                        classification={
                            "category": "very_short_haul",
                            "cabin_class": "economy",
                        },
                        values={"ef_kg_co2eq_per_km": 0.1},
                        year=2025,
                    ),
                ],
                current_job_id=job_plane_id,
            )
            await s.commit()

            f_plane = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                year=2025,
                classification={
                    "category": "very_short_haul",
                    "cabin_class": "economy",
                },
            )
            assert f_plane.id is not None
            plane_id: int = f_plane.id

            # ── Control: a different YEAR (2024) with its OWN stale row
            #    — must be untouched by delete_stale_for_year(2025). ────
            job_2024_v1 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2024,
                is_current=False,
            )
            s.add(job_2024_v1)
            await s.commit()
            assert job_2024_v1.id is not None
            job_2024_v1_id: int = job_2024_v1.id

            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "Old2024",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.1},
                        year=2024,
                    ),
                ],
                current_job_id=job_2024_v1_id,
            )
            await s.commit()

            job_2024_v2 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.equipment.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2024,
                is_current=True,
            )
            s.add(job_2024_v2)
            await s.commit()
            assert job_2024_v2.id is not None
            job_2024_v2_id: int = job_2024_v2.id

            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.equipment__it.value,
                        data_entry_type_id=DataEntryTypeEnum.it.value,
                        classification={
                            "equipment_class": "Laptop",
                            "sub_class": "New2024",
                        },
                        values={"ef_kg_co2eq_per_kwh": 0.2},
                        year=2024,
                    ),
                ],
                current_job_id=job_2024_v2_id,
            )
            await s.commit()

            f_2024_stale = await _factor_by_classification(
                s,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2024,
                classification={"equipment_class": "Laptop", "sub_class": "Old2024"},
            )
            assert f_2024_stale.id is not None
            stale_2024_id: int = f_2024_stale.id

            # ── Act — the ingest-scoped sweep the provider runs ──────
            deleted_count = await repo.delete_stale_for_year(
                2025,
                det_ids=[DataEntryTypeEnum.it.value],
                threshold_job_id=job2_id,
            )
            await s.commit()
    finally:
        await engine.dispose()

    assert deleted_count == 2, (
        "expected exactly the dropped Desktop row and the old-shape "
        f"Tablet/Standard row to be deleted; got count={deleted_count}"
    )

    async with _fresh_session(pg_dsn) as vs:
        remaining_ids = set((await vs.execute(select(Factor.id))).scalars().all())
        remaining_emission = await vs.get(DataEntryEmission, emission_id)

    assert drop_id not in remaining_ids, "dropped Desktop factor must be deleted"
    assert reshape_old_id not in remaining_ids, (
        "old-shape Tablet/Standard factor must be deleted"
    )
    assert keep_id in remaining_ids, "unchanged Laptop factor must survive"
    assert reshape_new_id in remaining_ids, "new-shape Tablet/Pro factor must survive"
    assert plane_id in remaining_ids, (
        "different det (plane), not stale, must be untouched by the sweep"
    )
    assert stale_2024_id in remaining_ids, (
        "different year (2024) stale row must be untouched by "
        "delete_stale_for_year(2025)"
    )
    assert remaining_emission is None, (
        "emission row referencing the deleted Desktop factor must be "
        "cascade-deleted via primary_factor_id's ondelete=CASCADE"
    )


@pytest.mark.asyncio
async def test_originating_bug_classification_reshape_no_multiple_results(pg_dsn):
    """#1661's originating bug, as a regression test.

    building_rooms factors were uploaded with a 2-key classification
    ``{building_name, room_type}``, then re-uploaded with a 3-key shape
    (``energy_type`` added).  The upsert identity includes
    ``classification::text``, so both generations survived and
    ``get_by_classification`` — which filters only on kind/subkind —
    raised ``MultipleResultsFound`` (HTTP 500 on
    ``GET /v1/factors/30/classes/{kind}/values``).

    Replace-semantics kills the class: after ``delete_stale_for_year``
    only the new generation remains and the lookup succeeds.  The
    pre-deletion ``MultipleResultsFound`` is asserted first to prove the
    repro is real, not vacuous.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    year = 2025
    two_key = {"building_name": "GC", "room_type": "miscellaneous"}
    three_key = {**two_key, "energy_type": "electric"}

    try:
        async with Sf() as s:
            repo = FactorRepository(s)

            job1 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.buildings.value,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                year=year,
                is_current=False,
            )
            s.add(job1)
            await s.commit()
            assert job1.id is not None
            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.buildings__rooms.value,
                        data_entry_type_id=DataEntryTypeEnum.building.value,
                        classification=dict(two_key),
                        values={"kwh_per_m2": 100.0},
                        year=year,
                    )
                ],
                current_job_id=job1.id,
            )
            await s.commit()

            job2 = _seed_factor_job(
                module_type_id=ModuleTypeEnum.buildings.value,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                year=year,
                is_current=True,
            )
            s.add(job2)
            await s.commit()
            assert job2.id is not None
            await repo.upsert_factors(
                [
                    Factor(
                        emission_type_id=EmissionType.buildings__rooms.value,
                        data_entry_type_id=DataEntryTypeEnum.building.value,
                        classification=dict(three_key),
                        values={"kwh_per_m2": 100.0},
                        year=year,
                    )
                ],
                current_job_id=job2.id,
            )
            await s.commit()

            # The repro: both generations match (kind, subkind) → 500 class.
            with pytest.raises(MultipleResultsFound):
                await FactorService(s).get_by_classification(
                    data_entry_type=DataEntryTypeEnum.building,
                    kind="GC",
                    subkind="miscellaneous",
                    year=year,
                )

            deleted = await repo.delete_stale_for_year(
                year,
                det_ids=[DataEntryTypeEnum.building.value],
                threshold_job_id=job2.id,
            )
            await s.commit()
            assert deleted == 1, f"expected the 2-key generation gone, got {deleted}"

            factor = await FactorService(s).get_by_classification(
                data_entry_type=DataEntryTypeEnum.building,
                kind="GC",
                subkind="miscellaneous",
                year=year,
            )
            assert factor is not None
            assert factor.classification == three_key
    finally:
        await engine.dispose()
