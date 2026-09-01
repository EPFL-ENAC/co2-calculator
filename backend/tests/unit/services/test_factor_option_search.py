"""#2391 decision 4 — server-side typeahead over classification options.

Purchase's option list (~17k UNSPSC codes) is too large to ship as a
taxonomy tree; `ModuleHandlerService.search_factor_options` answers a
typed search instead, matching the stored value, the English description,
and its translated label, with `locations/search`-style relevance
ordering. Works for the self-labeling shape too (equipment).
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.classification_translation import ClassificationTranslation
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService


def _purchase_factor(code: str, description: str | None, year: int = 2025) -> Factor:
    classification: dict = {"purchase_institutional_code": code}
    if description is not None:
        classification["purchase_institutional_description"] = description
    return Factor(
        emission_type_id=8,
        data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
        year=year,
        classification=classification,
        values={},
    )


async def _seed_purchase_factors(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            _purchase_factor("43211501", "Computer servers"),
            _purchase_factor("43211503", "Notebook computers"),
            _purchase_factor("27112700", "Power tools"),
            # Present-but-blank description: the code is the only text.
            _purchase_factor("95121800", None),
            # Wrong year — must never match.
            _purchase_factor("43211501", "Computer servers", year=2024),
            ClassificationTranslation(
                field_name="purchase_institutional_description",
                value="Computer servers",
                lang="fr",
                label="Serveurs informatiques",
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


async def _search(
    db_session: AsyncSession,
    query: str,
    lang: str,
    det: DataEntryTypeEnum = DataEntryTypeEnum.other_purchases,
    limit: int = 20,
):
    handler = BaseModuleHandler.get_by_type(det)
    service = ModuleHandlerService(db_session)
    return await service.search_factor_options(handler, det, 2025, query, lang, limit)


@pytest.mark.asyncio
async def test_english_search_ranks_starts_with_before_contains(
    db_session: AsyncSession,
):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "computer", "en")

    assert [(o.name, o.label) for o in options] == [
        ("43211501", "Computer servers"),
        ("43211503", "Notebook computers"),
    ]


@pytest.mark.asyncio
async def test_french_search_matches_translated_label(db_session: AsyncSession):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "serveur", "fr")

    assert [(o.name, o.label) for o in options] == [
        ("43211501", "Serveurs informatiques")
    ]


@pytest.mark.asyncio
async def test_english_text_still_matches_in_french_locale(
    db_session: AsyncSession,
):
    """A French-locale user typing the English term must still find it —
    and get the French label back.
    """
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "power", "fr")

    assert [(o.name, o.label) for o in options] == [("27112700", "Outils électriques")]


@pytest.mark.asyncio
async def test_untranslated_description_falls_back_to_english(
    db_session: AsyncSession,
):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "notebook", "fr")

    assert [(o.name, o.label) for o in options] == [("43211503", "Notebook computers")]


@pytest.mark.asyncio
async def test_code_search_matches_blank_description_row(
    db_session: AsyncSession,
):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "9512", "fr")

    assert [(o.name, o.label) for o in options] == [("95121800", "95121800")]


@pytest.mark.asyncio
async def test_limit_is_respected(db_session: AsyncSession):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "co", "en", limit=1)

    assert len(options) == 1


@pytest.mark.asyncio
async def test_duplicate_codes_collapse_to_one_option(db_session: AsyncSession):
    """The same code on several factor rows (one per additional code) must
    yield one option.
    """
    db_session.add_all(
        [
            _purchase_factor("27112700", "Power tools"),
            _purchase_factor("27112700", "Power tools kit"),
        ]
    )
    await db_session.commit()

    options = await _search(db_session, "power", "en")

    assert [o.name for o in options] == ["27112700"]


@pytest.mark.asyncio
async def test_like_metacharacters_match_literally(db_session: AsyncSession):
    """'100%' is a real substring of purchase descriptions, not a wildcard
    — and '_' must not act as any-character (review follow-up).
    """
    db_session.add(_purchase_factor("11111111", "100% cotton shirts"))
    await db_session.commit()
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "100%", "en")
    assert [o.name for o in options] == ["11111111"]

    options = await _search(db_session, "c_tton", "en")
    assert options == []


@pytest.mark.asyncio
async def test_query_is_trimmed_before_matching(db_session: AsyncSession):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "  serveur  ", "fr")

    assert [o.name for o in options] == ["43211501"]


@pytest.mark.asyncio
async def test_query_below_min_length_after_trim_returns_empty(
    db_session: AsyncSession,
):
    """' o ' passes the route's raw min_length=2 but is one character of
    signal — the typeahead contract is an empty list, not a scan.
    """
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, " o ", "en")

    assert options == []


@pytest.mark.asyncio
async def test_region_locale_normalizes_to_short_code(db_session: AsyncSession):
    await _seed_purchase_factors(db_session)

    options = await _search(db_session, "serveur", "fr-CH")

    assert [(o.name, o.label) for o in options] == [
        ("43211501", "Serveurs informatiques")
    ]


@pytest.mark.asyncio
async def test_self_labeling_shape_searches_values_and_translations(
    db_session: AsyncSession,
):
    db_session.add_all(
        [
            Factor(
                emission_type_id=2,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                year=2025,
                classification={"equipment_class": "Engine", "sub_class": None},
                values={},
            ),
            ClassificationTranslation(
                field_name="equipment_class",
                value="Engine",
                lang="fr",
                label="Moteurs",
            ),
        ]
    )
    await db_session.commit()

    english = await _search(db_session, "eng", "en", det=DataEntryTypeEnum.it)
    assert [(o.name, o.label) for o in english] == [("Engine", "Engine")]

    french = await _search(db_session, "moteur", "fr", det=DataEntryTypeEnum.it)
    assert [(o.name, o.label) for o in french] == [("Engine", "Moteurs")]
