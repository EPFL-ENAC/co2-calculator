"""#2401 / #2516 — the submodule search filter matches a translated label too.

`filter=serveur&lang=fr` must find a row stored as `equipment_class="server"`
(#2516's reported bug: searching in French found nothing). It must not do
the reverse (an English search matching only because some other language's
label happens to contain the term), and a value with no translation row
falls back to matching its own (English) stored value — the CSV convention
the ingestion side implements (#2401 plan).
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.classification_translation import ClassificationTranslation
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository


async def _seed_equipment_module(db_session: AsyncSession) -> int:
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.equipment.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add_all(
        [
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.it,
                status=DataEntryStatusEnum.PENDING,
                data={
                    "equipment_class": "server",
                    "name": "rack-1",
                    "active_usage_hours_per_week": 40,
                    "standby_usage_hours_per_week": 128,
                },
                year=2025,
            ),
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.it,
                status=DataEntryStatusEnum.PENDING,
                data={
                    "equipment_class": "laptop",
                    "name": "portable-1",
                    "active_usage_hours_per_week": 40,
                    "standby_usage_hours_per_week": 128,
                },
                year=2025,
            ),
        ]
    )
    db_session.add(
        ClassificationTranslation(
            field_name="equipment_class",
            value="server",
            lang="fr",
            label="serveur",
        )
    )
    await db_session.commit()
    return module.id


@pytest.mark.asyncio
async def test_french_filter_matches_translated_label(db_session: AsyncSession):
    module_id = await _seed_equipment_module(db_session)
    repo = DataEntryRepository(db_session)

    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter="serveur",
        lang="fr",
    )

    assert [item.equipment_class for item in response.items] == ["server"]


@pytest.mark.asyncio
async def test_untranslated_value_falls_back_to_english_match(
    db_session: AsyncSession,
):
    """No `equipment_class_fr` row for "laptop" — a French-locale search for
    its English value must still find it (the CSV's fallback semantics).
    """
    module_id = await _seed_equipment_module(db_session)
    repo = DataEntryRepository(db_session)

    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter="laptop",
        lang="fr",
    )

    assert [item.equipment_class for item in response.items] == ["laptop"]


@pytest.mark.asyncio
async def test_english_locale_does_not_match_other_languages_label(
    db_session: AsyncSession,
):
    """lang=en must not pick up the French translation table at all —
    searching the French word while in English should find nothing.
    """
    module_id = await _seed_equipment_module(db_session)
    repo = DataEntryRepository(db_session)

    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter="serveur",
        lang="en",
    )

    assert response.items == []
    assert response.summary.total_items == 0
