"""Cross-source-type recalc uniformity (Plan 310 test-coverage, Unit 6/11).

Pins the load-bearing property of
``EmissionRecalculationWorkflow.recalculate_for_data_entry_type``: the
workflow recomputes emissions UNIFORMLY across every
``DataEntrySourceEnum`` value because it filters on
``(data_entry_type_id, year)`` only — see
``backend/app/workflows/emission_recalculation.py:29-51`` and
``DataEntryRepository.list_by_data_entry_type_and_year`` which exposes no
``source`` parameter.

What this test guards against
-----------------------------
A future change that adds a ``source`` filter to either the workflow or
``list_by_data_entry_type_and_year`` would silently leave entries from
the other ingestion paths at a stale ``kg_co2eq`` after a factor
reupload.  Units 2-5 of the test-coverage batch each pin a single
ingestion path; this unit pins the cross-path invariant Units 2-5
implicitly assume.

Negative control
----------------
The test seeds three rows with three distinct ``source`` states on the
same ``(module, det, year)`` slice, swaps the matching factor's ef, runs
the recalc workflow ONCE, and asserts:

  1. Every row's ``kg_co2eq`` updated to the NEW factor's contribution.
  2. NO row was left at its initial ``kg_co2eq`` (the bug-case for a
     would-be ``source``-filtered workflow).
  3. NO row's ``source`` enum was mutated by the recompute (recalc must
     not touch source).

Plus a positive sanity check: the recompute is driven by the factor
swap, not by re-importing data — entry.data on each row is identical
before and after.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

from .conftest import seeded_year_with_units

# ---------------------------------------------------------------------------
# Test-data shape
# ---------------------------------------------------------------------------
#
# We use ``professional_travel.plane`` because the live system has all
# three active source-types feeding it (inline UI = NULL, BaseCSVProvider,
# external integration like Tableau).  Plane factors are keyed on
# ``classification.category`` (haul_category) and the formula multiplies
# ``ctx.distance_km * factor.ef_kg_co2eq_per_km * factor.rfi_adjustment``.
#
# To avoid seeding ``locations`` rows just to satisfy plane's
# ``pre_compute`` (which reads origin/destination IATA → Location to
# derive distance_km + haul_category), we stamp ``distance_km`` and
# ``haul_category`` directly into ``entry.data``.  ``pre_compute`` then
# returns ``{}`` (no Location resolved → early return) and the existing
# ``data_entry.data`` keys flow through to ctx unchanged — exact same
# code path the production recompute exercises once Locations are
# already cached on the row.
_YEAR = 2025
_HAUL = "long_haul"
_CABIN = "economy"
_DISTANCE_KM = 5_000.0
_RFI = 1.9
_INITIAL_EF = 0.10  # kg_co2eq per km
_NEW_EF = 0.25  # kg_co2eq per km — distinct so the diff is unambiguous


def _plane_entry_data(*, suffix: str) -> dict:
    """Return the ``data`` JSON for a single plane DataEntry.

    The ``user_institutional_id`` and ``origin_iata``/``destination_iata``
    fields are kept distinct per row so that nothing in the workflow can
    accidentally collapse two entries onto a single emission row via a
    natural-key-on-data join.
    """
    return {
        "user_institutional_id": f"USER-{suffix}",
        "origin_iata": f"O{suffix[:2].upper()}",
        "destination_iata": f"D{suffix[:2].upper()}",
        "cabin_class": _CABIN,
        "number_of_trips": 1,
        # Pre-stamped so the missing-Location branch in pre_compute is OK.
        "distance_km": _DISTANCE_KM,
        "haul_category": _HAUL,
    }


@pytest.mark.asyncio
async def test_recalc_uniform_across_source_types(pg_dsn) -> None:
    """Three plane DataEntries with three distinct ``source`` states all
    recompute against the new factor — none stays at its initial value,
    none has its ``source`` field mutated.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ── 1. Year tree + plane CRM ───────────────────────────────────────
    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=_YEAR, n_units=1)
    unit_id = seeded.units[0].id
    plane_crm: CarbonReportModule = seeded.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.professional_travel))
    ]
    crm_id = plane_crm.id

    # ── 2. Initial factor + 3 entries with distinct source states ──────
    # ``USER_MANUAL`` is represented as NULL on the column (the inline
    # UI shape doesn't always stamp the enum); the other two carry the
    # explicit enum values that the BaseCSVProvider and the Tableau
    # path persist today.  All three sit on the same
    # ``(data_entry_type_id, year)`` slice so the workflow's
    # ``list_by_data_entry_type_and_year`` returns every one of them.
    source_states: list[tuple[str, int | None]] = [
        ("manual", None),  # USER_MANUAL — inline UI shape
        ("csv", DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value),
        ("ext", DataEntrySourceEnum.EXTERNAL_INTEGRATION.value),
    ]
    async with Sf() as s:
        factor = Factor(
            emission_type_id=EmissionType.professional_travel__plane.value,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            classification={"category": _HAUL, "cabin_class": _CABIN},
            values={
                "ef_kg_co2eq_per_km": _INITIAL_EF,
                "rfi_adjustment": _RFI,
                "min_distance": 3500,
                "max_distance": 20000,
            },
            year=_YEAR,
        )
        s.add(factor)
        await s.commit()

        entry_ids: list[int] = []
        entry_data_snapshots: list[dict] = []
        for suffix, source_value in source_states:
            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.plane.value,
                carbon_report_module_id=crm_id,
                data=_plane_entry_data(suffix=suffix),
                source=source_value,
            )
            s.add(entry)
            await s.commit()
            entry_ids.append(entry.id)
            entry_data_snapshots.append(dict(entry.data))

    # ── 3. Initial emission compute for each entry ─────────────────────
    async with Sf() as s:
        emission_svc = DataEntryEmissionService(s)
        for entry_id in entry_ids:
            entry = (
                await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
            ).scalar_one()
            await emission_svc.upsert_by_data_entry(
                DataEntryResponse.model_validate(entry)
            )
        await s.commit()

    # Capture the initial kg_co2eq per entry — must be non-zero so the
    # post-recalc assertion proves a real recompute (not a no-op).
    initial_kg_by_entry: dict[int, float] = {}
    async with Sf() as s:
        for entry_id in entry_ids:
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
            total = sum((r.kg_co2eq or 0.0) for r in rows)
            assert total > 0, (
                f"initial compute for entry_id={entry_id} (source state) "
                f"should produce non-zero kg_co2eq; got {total}.  "
                "Likely cause: pre_compute couldn't resolve haul_category "
                "or factor lookup missed the seeded factor."
            )
            initial_kg_by_entry[entry_id] = total

    # All three entries share the same factor + same data shape, so
    # their initial totals must be identical (sanity for the "uniform
    # ground truth" the recalc has to land on).
    initial_values = set(initial_kg_by_entry.values())
    assert len(initial_values) == 1, (
        "all three entries must produce the same initial kg_co2eq — "
        f"got {initial_kg_by_entry}.  Diverging values would mean the "
        "test setup leaked source-specific data into the formula."
    )

    expected_initial = _DISTANCE_KM * _INITIAL_EF * _RFI
    assert next(iter(initial_values)) == pytest.approx(expected_initial, rel=1e-6)

    # ── 4. Swap the factor's ef — same identity, new value ─────────────
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor.id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_km": _NEW_EF}
        await s.commit()

    # ── 5. Run the recalc workflow ─────────────────────────────────────
    # No ``source`` argument; the contract is that every entry on the
    # (det, year) slice is recomputed regardless of its source state.
    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        result = await wf.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, _YEAR
        )
        await s.commit()

    assert result["recalculated"] == 3, (
        "workflow must visit every entry across all source states; "
        f"got {result!r}.  A regression that adds a source filter to "
        "list_by_data_entry_type_and_year would surface here as "
        "recalculated < 3."
    )
    assert result["errors"] == 0, f"unexpected per-entry errors: {result!r}"

    # ── 6. Verify on a SEPARATE engine — proves cross-connection commit
    expected_new_kg = _DISTANCE_KM * _NEW_EF * _RFI
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            for entry_id, snapshot, (suffix, expected_source) in zip(
                entry_ids, entry_data_snapshots, source_states, strict=True
            ):
                entry = (
                    await vs.execute(
                        select(DataEntry).where(col(DataEntry.id) == entry_id)
                    )
                ).scalar_one()

                # 6a. ``source`` was NOT mutated by the recompute.
                assert entry.source == expected_source, (
                    f"recalc must not mutate source — entry_id={entry_id} "
                    f"(suffix={suffix!r}) was {expected_source!r}, "
                    f"now {entry.source!r}"
                )

                # 6b. ``data`` was NOT silently re-imported — same dict
                #     before and after the recompute.  The workflow may
                #     refresh ``primary_factor_id`` for handlers with
                #     ``kind_field`` keys IN entry.data, but plane
                #     derives ``category`` only in pre_compute so the
                #     refresh gate is closed for this handler.
                assert entry.data == snapshot, (
                    f"recalc must not mutate entry.data — entry_id={entry_id} "
                    f"diff: before={snapshot!r}, after={entry.data!r}.  "
                    "kg_co2eq change must come from the factor swap, not "
                    "from a re-import."
                )

                # 6c. ``kg_co2eq`` reflects the NEW factor, not the old one.
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
                total = sum((r.kg_co2eq or 0.0) for r in rows)
                assert total == pytest.approx(expected_new_kg, rel=1e-6), (
                    f"entry_id={entry_id} (source={expected_source!r}) "
                    f"kg_co2eq={total} did not land on the post-swap "
                    f"target {expected_new_kg}.  Either the workflow "
                    "skipped this source state (regression — would mean "
                    "the workflow grew a source filter) or the factor "
                    "swap did not propagate."
                )
                # Expected NEW total is 2.5× the initial; comparing on a
                # direct ratio guards against a hypothetical no-op recalc
                # without the false-positive risk of ``!= approx(...)``.
                assert total > initial_kg_by_entry[entry_id] * 2.0, (
                    f"entry_id={entry_id} kg_co2eq={total} is still close "
                    f"to the pre-swap value {initial_kg_by_entry[entry_id]} — "
                    "recalc looks like a no-op for this row."
                )
    finally:
        await verify_engine.dispose()
        await engine.dispose()
