"""Integration regression: listing a plane submodule must NOT persist
computed fields back into ``DataEntry.data``.

This is the integration-shaped counterpart of the repo unit test in
``tests/unit/repositories/test_data_entry_repo.py::test_get_submodule_data_does_not_persist_computed_fields``.

The unit test exercises ``get_submodule_data`` against a DataEntry with
no emissions (so all the JOINs return NULL and the read code path is
partially covered). This test goes further:

- seeds a real ``DataEntryEmission`` row so the JOINs return a populated
  ``total_kg_co2eq`` and the enriched payload actually has values to
  inject — closer to the production path where the bug surfaced;
- triggers a follow-up DB write in the same session after listing
  (mimicking what happens during a normal request lifecycle when
  recompute / audit / stats updates flush dirty rows);
- re-reads the raw row through a fresh ORM lookup and asserts the JSON
  column is byte-identical to the original input.

Pre-fix (commit 804e1f79^), the listing dirty-flushed ``data_entry.data``
with ``kg_co2eq`` / ``primary_factor`` / ``distance_km`` /
``traveler_name`` keys; this test would fail. After the fix, the JSON
column stays clean regardless of how many flushes happen downstream.
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository

# Forbidden keys: derived/computed values that the listing endpoint
# enriches into the response payload and that must NEVER end up in the
# persisted ``data_entries.data`` JSON column.
COMPUTED_KEYS = (
    "kg_co2eq",
    "primary_factor",
    "traveler_name",
    "distance_km",
    "room_surface_square_meter",
)


@pytest.mark.asyncio
async def test_listing_plane_with_emissions_does_not_pollute_data(
    db_session: AsyncSession,
):
    """End-to-end: seed factor + module + plane DataEntry + emission, list
    via the submodule endpoint, commit, mutate something, commit again, and
    confirm the original ``data`` dict is preserved verbatim.
    """
    repo = DataEntryRepository(db_session)

    # ---------- arrange: realistic plane scenario ------------------------
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.NOT_STARTED,
    )
    db_session.add(module)
    await db_session.flush()

    factor = Factor(
        emission_type_id=EmissionType.professional_travel__plane.value,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        classification={"category": "very_short_haul", "year": 2025},
        values={
            "ef_kg_co2eq_per_km": 0.174,
            "rfi_adjustment": 2.7,
            "class_adjustement": 2,
        },
        year=2025,
    )
    db_session.add(factor)
    await db_session.flush()

    # The exact shape the user reported in the bug write-up: GVA→ZRH first
    # class, no precomputed kg_co2eq, primary_factor_id linked.
    original_data = {
        "origin_iata": "GVA",
        "destination_iata": "ZRH",
        "cabin_class": "first",
        "user_institutional_id": "150322",
        "number_of_trips": 1,
        "departure_date": "2025/01/09",
        "primary_factor_id": factor.id,
    }
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data=dict(original_data),
    )
    db_session.add(entry)
    await db_session.flush()
    entry_id = entry.id

    # Seed a populated emission so the JOINs in get_submodule_data return
    # non-NULL totals — this exercises the enrichment code path that
    # built the (previously persisted) ``primary_factor`` / ``kg_co2eq``
    # / ``distance_km`` keys.
    emission = DataEntryEmission(
        data_entry_id=entry_id,
        emission_type_id=EmissionType.professional_travel__plane.value,
        primary_factor_id=factor.id,
        kg_co2eq=152.685,
        additional_value=877.5,  # used as distance_km for travel entries
        scope=None,
        meta={},
    )
    db_session.add(emission)
    await db_session.commit()

    # ---------- act: list, then trigger downstream writes ---------------
    listing = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        limit=10,
        offset=0,
        sort_by="id",
        sort_order="asc",
    )

    # Confirm enrichment actually happened — the response items should
    # carry the computed fields. If they don't, the test setup is wrong
    # and the assertions below would pass vacuously.
    assert listing.count == 1, "expected exactly one listed plane entry"

    # Now do something that would naturally flush the session in a real
    # request — e.g. updating an unrelated emission. Pre-fix, this is what
    # caused the dirty data_entry to be persisted.
    emission.kg_co2eq = 200.0
    db_session.add(emission)
    await db_session.commit()

    # ---------- assert: the JSON column is unchanged --------------------
    db_session.expire_all()
    refreshed = (
        await db_session.execute(select(DataEntry).where(DataEntry.id == entry_id))
    ).scalar_one()

    assert refreshed.data == original_data, (
        f"DataEntry.data was mutated by the listing pipeline.\n"
        f"  expected: {original_data!r}\n"
        f"  actual:   {refreshed.data!r}"
    )
    for key in COMPUTED_KEYS:
        assert key not in refreshed.data, (
            f"computed key {key!r} leaked into DataEntry.data: {refreshed.data!r}"
        )


@pytest.mark.asyncio
async def test_repeated_listings_dont_compound_pollution(
    db_session: AsyncSession,
):
    """Stress variant: list the same submodule three times with a flush
    between each, and confirm ``data`` is still pristine. Catches the
    case where a partial fix only prevents the first listing from
    polluting but a later one still does.
    """
    repo = DataEntryRepository(db_session)

    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.NOT_STARTED,
    )
    db_session.add(module)
    await db_session.flush()

    original_data = {
        "origin_iata": "CDG",
        "destination_iata": "JFK",
        "cabin_class": "eco",
        "user_institutional_id": "u1",
        "number_of_trips": 1,
        "primary_factor_id": None,
    }
    entry = DataEntry(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data=dict(original_data),
    )
    db_session.add(entry)
    await db_session.commit()
    entry_id = entry.id

    for _ in range(3):
        await repo.get_submodule_data(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            limit=10,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )
        await db_session.commit()

    db_session.expire_all()
    refreshed = (
        await db_session.execute(select(DataEntry).where(DataEntry.id == entry_id))
    ).scalar_one()
    assert refreshed.data == original_data
