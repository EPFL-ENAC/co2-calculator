"""#2401 review follow-up — the top-class breakdown carries backend labels.

The results chart used to resolve purchase segment labels from the deleted
`i18n/purchase_factors.ts` (`$te(<code>)`); the old backend enrichment read
`Factor.values["translation_key"]`, which purchase factors never carried,
so it silently attached nothing. `enrich_breakdown_with_labels` now
resolves a request-locale `label` per child through the same two shapes as
the taxonomy builder — the chart renders that field, never an i18n table.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.classification_translation import ClassificationTranslation
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.services.data_entry_emission_service import DataEntryEmissionService

YEAR = 2025


async def _seed(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Factor(
                emission_type_id=8,
                data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
                year=YEAR,
                classification={
                    "purchase_institutional_code": "43211501",
                    "purchase_institutional_description": "Computer servers",
                },
                values={},
            ),
            ClassificationTranslation(
                field_name="purchase_institutional_description",
                value="Computer servers",
                lang="fr",
                label="Serveurs informatiques",
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


def _breakdown() -> list[dict]:
    return [
        {
            "name": "purchases",
            "children": [
                {"name": "43211501", "value": 10.0},
                {"name": "99999999", "value": 5.0},
                {"name": "rest", "value": 1.0},
            ],
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lang", "expected"),
    [("en", "Computer servers"), ("fr-CH", "Serveurs informatiques")],
)
async def test_code_shape_resolves_description_per_locale(
    db_session: AsyncSession, lang: str, expected: str
):
    await _seed(db_session)
    service = DataEntryEmissionService(db_session)

    enriched = await service.enrich_breakdown_with_labels(
        breakdown=_breakdown(),
        data_entry_types=[DataEntryTypeEnum.other_purchases],
        group_by_field="purchase_institutional_code",
        lang=lang,
        report_year=YEAR,
    )

    children = {c["name"]: c for c in enriched[0]["children"]}
    assert children["43211501"]["label"] == expected
    # No factor text for this code — the code is the only label there is.
    assert children["99999999"]["label"] == "99999999"
    assert "label" not in children["rest"]


@pytest.mark.asyncio
async def test_self_labeling_shape_translates_the_value(
    db_session: AsyncSession,
):
    await _seed(db_session)
    service = DataEntryEmissionService(db_session)

    breakdown = [{"name": "scientific", "children": [{"name": "Engine", "value": 1.0}]}]
    enriched = await service.enrich_breakdown_with_labels(
        breakdown=breakdown,
        data_entry_types=[DataEntryTypeEnum.it],
        group_by_field="equipment_class",
        lang="fr",
        report_year=YEAR,
    )

    assert enriched[0]["children"][0]["label"] == "Moteurs"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lang", "expected"), [("en", "Rodents"), ("fr-CH", "Rongeurs")]
)
async def test_translated_code_shape_labels_english_too(
    db_session: AsyncSession, lang: str, expected: str
):
    """Animal-facility bars group by `researchfacility_type`, a translated
    code field (#2613): the seeded label applies in EVERY locale, English
    included — before, English showed the raw `rodent` slug.
    """
    db_session.add_all(
        [
            ClassificationTranslation(
                field_name="researchfacility_type",
                value="rodent",
                lang="en",
                label="Rodents",
            ),
            ClassificationTranslation(
                field_name="researchfacility_type",
                value="rodent",
                lang="fr",
                label="Rongeurs",
            ),
        ]
    )
    await db_session.commit()
    service = DataEntryEmissionService(db_session)

    breakdown = [{"name": "animals", "children": [{"name": "rodent", "value": 2.0}]}]
    enriched = await service.enrich_breakdown_with_labels(
        breakdown=breakdown,
        data_entry_types=[DataEntryTypeEnum.animal_facilities],
        group_by_field="researchfacility_type",
        lang=lang,
        report_year=YEAR,
    )

    assert enriched[0]["children"][0]["label"] == expected
