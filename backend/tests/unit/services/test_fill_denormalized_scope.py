"""Regression tests for central denormalized-scope stamping.

Stage incident 2026-07-17: API providers built DataEntry rows without
``year``/``unit_id``, so the per-year cross-source replace DELETE (keyed
on ``data_entries.year``) never matched them and CSV re-uploads
mass-collided on DUPLICATE_INSTITUTIONAL_ID. The stamp now lives in ONE
place — ``DataEntryService.fill_denormalized_scope``, called by every
write path (create / bulk_create / bulk_copy) — so no provider can
forget it.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.services.data_entry_service import DataEntryService


async def _seed_module(db_session: AsyncSession) -> CarbonReportModule:
    report = CarbonReport(unit_id=42, year=2025, carbon_project_id=1)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=0,
    )
    db_session.add(module)
    await db_session.flush()
    return module


@pytest.mark.asyncio
async def test_fill_stamps_year_and_unit_id_from_carbon_report(
    db_session: AsyncSession,
):
    module = await _seed_module(db_session)
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.member.value,
        carbon_report_module_id=module.id,
        data={"user_institutional_id": "123456", "sius_code": "51"},
    )

    await DataEntryService(db_session).fill_denormalized_scope([entry])

    assert entry.year == 2025
    assert entry.unit_id == 42


@pytest.mark.asyncio
async def test_fill_never_overwrites_existing_values(db_session: AsyncSession):
    module = await _seed_module(db_session)
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.member.value,
        carbon_report_module_id=module.id,
        data={},
        year=2024,
        unit_id=7,
    )

    await DataEntryService(db_session).fill_denormalized_scope([entry])

    assert entry.year == 2024
    assert entry.unit_id == 7


@pytest.mark.asyncio
async def test_fill_is_a_noop_when_all_entries_are_stamped(
    db_session: AsyncSession,
):
    # No query fired for fully-stamped batches — assert via no module rows
    # needed: an unknown module id with values set is left untouched.
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.member.value,
        carbon_report_module_id=999999,
        data={},
        year=2025,
        unit_id=1,
    )
    await DataEntryService(db_session).fill_denormalized_scope([entry])
    assert entry.year == 2025
