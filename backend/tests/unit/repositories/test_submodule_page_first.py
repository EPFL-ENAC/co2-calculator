"""#2404 page-first pagination in ``get_submodule_data``.

The full statement joins per-row factor resolution and aggregates the
module's entire emission set to serve one page — 18,620 of 20,912 buffers
on a measured 20-row request went to rows the LIMIT then discarded. When
sort/filter read nothing outside ``data_entries``, the repo now resolves
the page's ids first and restricts both expensive branches to them.

The one thing this must not change is *what* comes back: which rows, in
which order, with which kg totals and which resolved factor. So the core
test here is an equivalence test — the same call through the page-first
path and through the original shape (page-first force-disabled) must
produce byte-identical responses, including across an offset boundary,
which is where a double-applied offset would silently return an empty or
wrong page while every same-page test stayed green.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import (
    DataEntry,
    DataEntryStatusEnum,
    DataEntryTypeEnum,
)
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions.taxonomy import EmissionType
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.data_entry import BaseModuleHandler


async def _seed_purchase_module(db_session: AsyncSession, n_entries: int = 7) -> int:
    """A purchase module with it_equipment entries, emissions and matching
    factors — the exact shape of the #2404 incident, so every branch
    page-first touches (emission aggregate, per-row factor resolution) has
    real data to get wrong.
    """
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.purchase.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    codes = ["A100", "B200", "C300"]
    for code in codes:
        db_session.add(
            Factor(
                emission_type_id=EmissionType.purchases__it_equipment.value,
                data_entry_type_id=DataEntryTypeEnum.it_equipment.value,
                year=2025,
                classification={"purchase_institutional_code": code},
                values={"kg_co2eq_per_currency": 0.5},
            )
        )
    entries = []
    for i in range(n_entries):
        entry = DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.it_equipment,
            status=DataEntryStatusEnum.PENDING,
            data={
                "purchase_institutional_code": codes[i % len(codes)],
                "name": f"entry-{i:02d}",
                "total_spent_amount": 100 + i,
            },
            year=2025,
        )
        db_session.add(entry)
        entries.append(entry)
    await db_session.flush()
    for i, entry in enumerate(entries):
        db_session.add(
            DataEntryEmission(
                data_entry_id=entry.id,
                emission_type_id=EmissionType.purchases__it_equipment.value,
                kg_co2eq=100.0 * (i + 1),
            )
        )
    await db_session.commit()
    return module.id


def _dump(response):
    return {
        "items": [item.model_dump() for item in response.items],
        "count": response.count,
        "total_items": response.summary.total_items,
        "has_more": response.has_more,
    }


async def _both_paths(repo: DataEntryRepository, **kwargs):
    fast = await repo.get_submodule_data(**kwargs)
    with patch.object(
        DataEntryRepository,
        "_page_first_entry_ids",
        new=AsyncMock(return_value=None),
    ):
        slow = await repo.get_submodule_data(**kwargs)
    return _dump(fast), _dump(slow)


@pytest.mark.asyncio
async def test_page_first_equals_full_shape_across_pages(db_session: AsyncSession):
    """Every page, both sort orders: identical items, order, kg totals,
    resolved factors, counts. Page 2 is the case that catches a
    double-applied offset.
    """
    module_id = await _seed_purchase_module(db_session)
    repo = DataEntryRepository(db_session)

    for offset in (0, 3, 6):
        for sort_order in ("asc", "desc"):
            fast, slow = await _both_paths(
                repo,
                carbon_report_module_id=module_id,
                data_entry_type_id=DataEntryTypeEnum.it_equipment.value,
                limit=3,
                offset=offset,
                sort_by="name",
                sort_order=sort_order,
            )
            assert fast == slow, f"diverged at offset={offset} order={sort_order}"
    # sanity against a vacuous pass: the pages carry real data
    assert fast["total_items"] == 7
    assert fast["items"]  # last page (offset 6) still has one row


@pytest.mark.asyncio
async def test_page_first_equals_full_shape_with_filter(db_session: AsyncSession):
    """An entry-local name filter stays eligible: pagination happens over
    the filtered set, identically in both shapes.
    """
    module_id = await _seed_purchase_module(db_session)
    repo = DataEntryRepository(db_session)

    fast, slow = await _both_paths(
        repo,
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.it_equipment.value,
        limit=2,
        offset=2,
        sort_by="id",
        sort_order="asc",
        filter="entry-0",  # matches entry-00 … entry-06
    )
    assert fast == slow
    assert fast["total_items"] == 7
    assert fast["count"] == 2


@pytest.mark.asyncio
async def test_page_first_actually_engages(db_session: AsyncSession):
    """Guard against the silent no-op: for an eligible call the ids helper
    must return the page, not None — otherwise every equivalence test above
    passes while the optimization is dead.
    """
    module_id = await _seed_purchase_module(db_session)
    repo = DataEntryRepository(db_session)
    handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum.it_equipment)
    ids = await repo._page_first_entry_ids(
        handler=handler,
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.it_equipment.value,
        limit=3,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter=None,
        exclude_planner_snapshots=False,
        is_equipment_entry=False,
    )
    assert ids is not None and len(ids) == 3


def test_eligibility_rules():
    """The gate itself: emission-backed and factor-backed sorts must fall
    back to the original shape; entry-local ones must not.
    """
    repo = DataEntryRepository.__new__(DataEntryRepository)
    purchase = BaseModuleHandler.get_by_type(DataEntryTypeEnum.it_equipment)
    process = BaseModuleHandler.get_by_type(DataEntryTypeEnum.process_emissions)
    equipment = BaseModuleHandler.get_by_type(DataEntryTypeEnum.scientific)

    assert repo._page_first_eligible(purchase, "id", None)
    assert repo._page_first_eligible(purchase, "name", None)
    # emission-aggregate-backed
    assert not repo._page_first_eligible(purchase, "kg_co2eq", None)
    # factor-backed sort (equipment sub_class coalesces Factor.classification)
    assert not repo._page_first_eligible(equipment, "sub_class", None)
    # process sorts category through Factor.classification -- ineligible
    assert not repo._page_first_eligible(process, "category", None)
    # process's filter_map is factor-backed: any effective filter disqualifies
    assert not repo._page_first_eligible(process, "id", "Refrig")
    # ...but a wildcard-only "filter" is a no-op and stays eligible
    assert repo._page_first_eligible(process, "id", "%")
    # unknown key: fall back; the main path raises its usual ValueError
    assert not repo._page_first_eligible(purchase, "no_such_column", None)
