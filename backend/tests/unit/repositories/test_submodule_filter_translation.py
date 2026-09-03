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


@pytest.mark.asyncio
async def test_sort_orders_by_translated_label(db_session: AsyncSession):
    """#2401 follow-up: a French table sorts French-alphabetically —
    ``sort_by`` a translatable column orders by the translated label,
    falling back to the stored English value where no row exists.
    """
    module_id = await _seed_equipment_module(db_session)
    # "laptop" sorts before "server" in English, but its French label
    # ("zzz ...") sorts after "serveur" — decisive either way.
    db_session.add(
        ClassificationTranslation(
            field_name="equipment_class",
            value="laptop",
            lang="fr",
            label="zzz ordinateur portable",
        )
    )
    await db_session.commit()
    repo = DataEntryRepository(db_session)

    async def _classes(lang: str) -> list[str]:
        response = await repo.get_submodule_data(
            carbon_report_module_id=module_id,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            limit=100,
            offset=0,
            sort_by="equipment_class",
            sort_order="asc",
            lang=lang,
        )
        return [item.equipment_class for item in response.items]

    assert await _classes("en") == ["laptop", "server"]
    assert await _classes("fr") == ["server", "laptop"]


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


async def _seed_headcount_module(db_session: AsyncSession) -> int:
    """Sius labels are seeded reference data (en AND fr — the stored value
    is a code in any locale); rows mirror migration 3b5609f893f4.
    """
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.headcount.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    def _member(name: str, sius_code: str) -> DataEntry:
        return DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.member,
            status=DataEntryStatusEnum.PENDING,
            data={"name": name, "sius_code": sius_code, "fte": 1.0},
            year=2025,
        )

    def _sius(value: str, lang: str, label: str) -> ClassificationTranslation:
        return ClassificationTranslation(
            field_name="sius_code", value=value, lang=lang, label=label
        )

    db_session.add_all(
        [
            _member("member-prof", "51"),
            _member("member-admin", "57"),
            _sius("51", "en", "Professors"),
            _sius(
                "51",
                "fr",
                "Enseignant·e·s habilité·e·s à diriger une unité organisationnelle",
            ),
            _sius("57", "en", "Administrative staff"),
            _sius("57", "fr", "Personnel administratif"),
        ]
    )
    await db_session.commit()
    return module.id


async def _member_codes(
    db_session: AsyncSession,
    module_id: int,
    lang: str,
    filter: str | None = None,
    sort_by: str = "id",
) -> list[str]:
    repo = DataEntryRepository(db_session)
    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.member.value,
        limit=100,
        offset=0,
        sort_by=sort_by,
        sort_order="asc",
        filter=filter,
        lang=lang,
    )
    return [item.sius_code for item in response.items]


async def _seed_rooms_module(db_session: AsyncSession) -> int:
    """Rooms' heating source (`energy_type`) lives on the resolved det-30
    factor, never on the entry; labels are seeded reference data for both
    languages (rows mirror migration fd12a7a0946f).
    """
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.buildings.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    def _room(name: str, room_type: str) -> DataEntry:
        return DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.building,
            status=DataEntryStatusEnum.PENDING,
            data={
                "building_name": "AAB",
                "room_name": name,
                "room_type": room_type,
            },
            year=2025,
        )

    def _room_factor(room_type: str, energy_type: str) -> Factor:
        return Factor(
            emission_type_id=2,
            data_entry_type_id=DataEntryTypeEnum.building.value,
            year=2025,
            classification={
                "building_name": "AAB",
                "room_type": room_type,
                "energy_type": energy_type,
            },
            values={},
        )

    def _energy(value: str, lang: str, label: str) -> ClassificationTranslation:
        return ClassificationTranslation(
            field_name="energy_type", value=value, lang=lang, label=label
        )

    db_session.add_all(
        [
            _room("room-a", "office"),
            _room("room-b", "laboratories"),
            _room_factor("office", "electric"),
            _room_factor("laboratories", "thermal"),
            _energy("electric", "en", "Electric"),
            _energy("electric", "fr", "Électrique"),
            _energy("thermal", "en", "Thermal"),
            _energy("thermal", "fr", "Thermique"),
        ]
    )
    await db_session.commit()
    return module.id


async def _room_rows(
    db_session: AsyncSession,
    module_id: int,
    lang: str,
    filter: str | None = None,
    sort_by: str = "id",
):
    repo = DataEntryRepository(db_session)
    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.building.value,
        limit=100,
        offset=0,
        sort_by=sort_by,
        sort_order="asc",
        filter=filter,
        lang=lang,
        factor_year=2025,
    )
    return response.items


@pytest.mark.asyncio
async def test_energy_type_filter_matches_label_via_the_factor(
    db_session: AsyncSession,
):
    """The filtered column is the JOINED factor's energy_type: the raw
    code, the English label and the French label all match — one search
    behavior in every locale, for a value the entry never stores.
    """
    module_id = await _seed_rooms_module(db_session)

    # 'lectrique' rather than 'électrique': sqlite's LIKE only case-folds
    # ASCII, so the label's leading 'É' wouldn't match a lowercase 'é'
    # here — Postgres ILIKE handles it, covered by the live stack.
    fr = await _room_rows(db_session, module_id, "fr", filter="lectrique")
    assert [i.room_name for i in fr] == ["room-a"]

    en = await _room_rows(db_session, module_id, "en", filter="Thermal")
    assert [i.room_name for i in en] == ["room-b"]

    raw = await _room_rows(db_session, module_id, "en", filter="electric")
    assert [i.room_name for i in raw] == ["room-a"]


@pytest.mark.asyncio
async def test_energy_type_labels_ride_rooms_rows(db_session: AsyncSession):
    """Rows carry the seeded label in the request locale even though the
    value lives only on the resolved factor; sort by energy_type orders
    by it without error.
    """
    module_id = await _seed_rooms_module(db_session)

    # fr asc puts room-b first under sqlite's byte collation ('T' < 'É');
    # the flip versus the raw-value order (electric < thermal) is exactly
    # what proves the sort reads the label, not the stored code. Postgres
    # collates the accent correctly on the live stack.
    fr = await _room_rows(db_session, module_id, "fr", sort_by="energy_type")
    assert [(i.room_name, (i.labels or {}).get("energy_type")) for i in fr] == [
        ("room-b", "Thermique"),
        ("room-a", "Électrique"),
    ]

    en = await _room_rows(db_session, module_id, "en", sort_by="energy_type")
    assert [(i.labels or {}).get("energy_type") for i in en] == [
        "Electric",
        "Thermal",
    ]


@pytest.mark.asyncio
async def test_sius_filter_matches_label_in_both_languages(
    db_session: AsyncSession,
):
    """Sius is a `translated_code_field`: the label subquery applies in
    EVERY language — one search behavior, English included.
    """
    module_id = await _seed_headcount_module(db_session)

    assert await _member_codes(db_session, module_id, "fr", "enseignant") == ["51"]
    assert await _member_codes(db_session, module_id, "en", "administrative") == ["57"]
    # The raw code keeps matching regardless of locale.
    assert await _member_codes(db_session, module_id, "en", "57") == ["57"]


@pytest.mark.asyncio
async def test_sius_sort_orders_by_label_per_language(db_session: AsyncSession):
    """En asc: Administrative(57) < Professors(51); fr asc: Enseignant(51)
    < Personnel administratif(57) — a raw-code sort would never flip.
    """
    module_id = await _seed_headcount_module(db_session)

    assert await _member_codes(db_session, module_id, "en", sort_by="sius_code") == [
        "57",
        "51",
    ]
    assert await _member_codes(db_session, module_id, "fr", sort_by="sius_code") == [
        "51",
        "57",
    ]


@pytest.mark.asyncio
async def test_description_of_other_det_never_matches(db_session: AsyncSession):
    """Review follow-up: seven purchase dets share these classification
    fields — the factor hop must only consult THIS det's catalog.
    """
    module_id = await _seed_purchase_module(db_session)
    db_session.add(
        Factor(
            emission_type_id=8,
            data_entry_type_id=DataEntryTypeEnum.it_equipment.value,
            year=2025,
            classification={
                # Same code as a seeded other_purchases entry, but the
                # matching description lives on another det's factor row.
                "purchase_institutional_code": "44121600",
                "purchase_institutional_description": "Power adapters",
            },
            values={},
        )
    )
    await db_session.commit()

    codes = await _filter_purchase(db_session, module_id, "power", "en")

    assert codes == ["27112700"]


@pytest.mark.asyncio
async def test_other_years_description_never_matches(db_session: AsyncSession):
    """A past year's description text must not match rows the current
    catalog describes differently (factor_year scopes the hop).
    """
    module_id = await _seed_purchase_module(db_session)
    db_session.add(
        Factor(
            emission_type_id=8,
            data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
            year=2024,
            classification={
                "purchase_institutional_code": "44121600",
                "purchase_institutional_description": "Power strips",
            },
            values={},
        )
    )
    await db_session.commit()

    repo = DataEntryRepository(db_session)
    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter="power",
        lang="en",
        factor_year=2025,
    )

    assert [i.purchase_institutional_code for i in response.items] == ["27112700"]


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


async def _seed_energy_module(db_session: AsyncSession) -> int:
    """Fuel names are enum keys labeled by the #2613 seed in BOTH languages
    (rows mirror migration 7bff78de3264): 'Natural gas' never matched the
    stored `natural_gas` before, in any locale.
    """
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.buildings.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()

    def _entry(fuel: str) -> DataEntry:
        return DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.energy_combustion,
            status=DataEntryStatusEnum.PENDING,
            data={"name": fuel, "quantity": 10},
            year=2025,
        )

    def _fuel(value: str, lang: str, label: str) -> ClassificationTranslation:
        return ClassificationTranslation(
            field_name="name", value=value, lang=lang, label=label
        )

    db_session.add_all(
        [
            _entry("natural_gas"),
            _entry("heating_oil"),
            _fuel("natural_gas", "en", "Natural gas"),
            _fuel("natural_gas", "fr", "Gaz naturel"),
            _fuel("heating_oil", "en", "Heating oil"),
            _fuel("heating_oil", "fr", "Mazout"),
        ]
    )
    await db_session.commit()
    return module.id


async def _fuel_rows(
    db_session: AsyncSession,
    module_id: int,
    lang: str,
    filter: str | None = None,
    sort_by: str = "id",
):
    repo = DataEntryRepository(db_session)
    response = await repo.get_submodule_data(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
        limit=100,
        offset=0,
        sort_by=sort_by,
        sort_order="asc",
        filter=filter,
        lang=lang,
        factor_year=2025,
    )
    return response.items


@pytest.mark.asyncio
async def test_fuel_filter_matches_label_in_both_languages(
    db_session: AsyncSession,
):
    """`name` is a `translated_code_field` (#2613): the space in
    'Natural gas' proves the label subquery matched, not the raw
    ILIKE on `natural_gas` — English included.
    """
    module_id = await _seed_energy_module(db_session)

    en = await _fuel_rows(db_session, module_id, "en", filter="Natural gas")
    assert [i.name for i in en] == ["natural_gas"]

    fr = await _fuel_rows(db_session, module_id, "fr", filter="Mazout")
    assert [i.name for i in fr] == ["heating_oil"]

    raw = await _fuel_rows(db_session, module_id, "fr", filter="natural_gas")
    assert [i.name for i in raw] == ["natural_gas"]


@pytest.mark.asyncio
async def test_fuel_sort_and_labels_per_language(db_session: AsyncSession):
    """En asc: Heating oil < Natural gas; fr asc: Gaz naturel < Mazout —
    the flip proves the sort reads the label. Rows carry the label in the
    request locale, English included.
    """
    module_id = await _seed_energy_module(db_session)

    en = await _fuel_rows(db_session, module_id, "en", sort_by="name")
    assert [(i.name, (i.labels or {}).get("name")) for i in en] == [
        ("heating_oil", "Heating oil"),
        ("natural_gas", "Natural gas"),
    ]

    fr = await _fuel_rows(db_session, module_id, "fr", sort_by="name")
    assert [(i.labels or {}).get("name") for i in fr] == [
        "Gaz naturel",
        "Mazout",
    ]


@pytest.mark.asyncio
async def test_room_type_filter_and_labels(db_session: AsyncSession):
    """room_type joined the translated-code shape in #2613: the French
    label matches the filter and rides the row's labels.
    """
    module_id = await _seed_rooms_module(db_session)
    db_session.add_all(
        [
            ClassificationTranslation(
                field_name="room_type", value="office", lang="en", label="Office"
            ),
            ClassificationTranslation(
                field_name="room_type", value="office", lang="fr", label="Bureau"
            ),
            ClassificationTranslation(
                field_name="room_type",
                value="laboratories",
                lang="fr",
                label="Laboratoires",
            ),
        ]
    )
    await db_session.commit()

    fr = await _room_rows(db_session, module_id, "fr", filter="Bureau")
    assert [i.room_name for i in fr] == ["room-a"]

    rows = await _room_rows(db_session, module_id, "fr")
    labels = {i.room_name: (i.labels or {}).get("room_type") for i in rows}
    assert labels == {"room-a": "Bureau", "room-b": "Laboratoires"}
