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
from app.models.factor import Factor
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


def _purchase_entry(module_id: int, name: str, code: str) -> DataEntry:
    return DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.other_purchases,
        status=DataEntryStatusEnum.PENDING,
        data={
            "name": name,
            "supplier": "supplier-1",
            "quantity": 1,
            "total_spent_amount": 10.0,
            "currency": "chf",
            "purchase_institutional_code": code,
        },
        year=2025,
    )


async def _seed_purchase_module(db_session: AsyncSession) -> int:
    """Purchase's code + label-field shape: the entry stores only the opaque
    UNSPSC code; the searchable text (English description, French label)
    lives on the factor / translation table.
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

    db_session.add_all(
        [
            _purchase_entry(module.id, "travel adapter", "27112700"),
            _purchase_entry(module.id, "mounting strips", "44121600"),
            # No factor row at all for this code — its only display text is
            # the code itself.
            _purchase_entry(module.id, "mystery item", "99999999"),
            Factor(
                emission_type_id=8,
                data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
                year=2025,
                classification={
                    "purchase_institutional_code": "27112700",
                    "purchase_institutional_description": "Power tools",
                },
                values={},
            ),
            Factor(
                emission_type_id=8,
                data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
                year=2025,
                classification={
                    "purchase_institutional_code": "44121600",
                    "purchase_institutional_description": "Adhesives",
                },
                values={},
            ),
            ClassificationTranslation(
                field_name="purchase_institutional_description",
                value="Power tools",
                lang="fr",
                label="Outils électriques",
            ),
        ]
    )
    await db_session.commit()
    return module.id


async def _purchase_response(
    db_session: AsyncSession, module_id: int, filter: str | None, lang: str
):
    repo = DataEntryRepository(db_session)
    return await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter=filter,
        lang=lang,
    )


async def _filter_purchase(
    db_session: AsyncSession, module_id: int, filter: str, lang: str
) -> list[str]:
    response = await _purchase_response(db_session, module_id, filter, lang)
    return [item.purchase_institutional_code for item in response.items]


@pytest.mark.asyncio
async def test_french_filter_matches_code_via_translated_description(
    db_session: AsyncSession,
):
    """#2401 follow-up: `filter=outils&lang=fr` finds the row whose stored
    code resolves (through the factor's description) to a description whose
    French label contains "outils".
    """
    module_id = await _seed_purchase_module(db_session)

    codes = await _filter_purchase(db_session, module_id, "outils", "fr")

    assert codes == ["27112700"]


@pytest.mark.asyncio
async def test_english_filter_matches_code_via_description(
    db_session: AsyncSession,
):
    """The same hop must work in English: the description isn't stored on
    the entry either, only on the factor.
    """
    module_id = await _seed_purchase_module(db_session)

    codes = await _filter_purchase(db_session, module_id, "power tools", "en")

    assert codes == ["27112700"]


@pytest.mark.asyncio
async def test_english_locale_does_not_match_french_description_label(
    db_session: AsyncSession,
):
    module_id = await _seed_purchase_module(db_session)

    codes = await _filter_purchase(db_session, module_id, "outils", "en")

    assert codes == []


@pytest.mark.asyncio
async def test_rows_carry_localized_labels_for_code_shape(
    db_session: AsyncSession,
):
    """#2401: table rows carry their own display label for the code +
    label-field shape — French when a translation row exists, the English
    description otherwise, the bare code when no factor text exists — so
    the frontend renders without fetching the (huge) purchase taxonomy.
    """
    module_id = await _seed_purchase_module(db_session)

    response = await _purchase_response(db_session, module_id, None, "fr")

    labels = {i.purchase_institutional_code: i.labels for i in response.items}
    assert labels["27112700"] == {"purchase_institutional_code": "Outils électriques"}
    assert labels["44121600"] == {"purchase_institutional_code": "Adhesives"}
    assert labels["99999999"] == {"purchase_institutional_code": "99999999"}


@pytest.mark.asyncio
async def test_rows_carry_english_description_labels(db_session: AsyncSession):
    """lang=en still needs the label on the row: the description lives on
    the factor, not on the entry.
    """
    module_id = await _seed_purchase_module(db_session)

    response = await _purchase_response(db_session, module_id, None, "en")

    labels = {i.purchase_institutional_code: i.labels for i in response.items}
    assert labels["27112700"] == {"purchase_institutional_code": "Power tools"}


@pytest.mark.asyncio
async def test_self_labeling_rows_labeled_only_when_translated(
    db_session: AsyncSession,
):
    """Self-labeling shape (equipment): the stored value already is the
    English label, so `labels` appears only where a translation row exists.
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
        lang="fr",
    )

    by_class = {i.equipment_class: i.labels for i in response.items}
    assert by_class["server"] == {"equipment_class": "serveur"}
    assert by_class["laptop"] is None

    english = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        lang="en",
    )
    assert all(i.labels is None for i in english.items)
