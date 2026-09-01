"""#2401 / #2391 — Postgres-only behavior of the translation stack.

The sqlite unit suite covers the logic; what it cannot exercise is the
Postgres SQL this feature actually runs in production: the
``ON CONFLICT (field_name, value, lang)`` upsert (`pg_insert`), JSONB
``->>`` matching inside the submodule search filter's factor hop, and the
typeahead's ``DISTINCT`` + relevance ``CASE`` ordering (Postgres requires
every DISTINCT ORDER BY expression in the select list — a rule sqlite
doesn't enforce). Lives in the ``_pg`` suite next to the other
real-Postgres factor tests, per that suite's placement rationale.
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.classification_translation import ClassificationTranslation
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import UserProvider
from app.repositories.classification_translation_repo import (
    ClassificationTranslationRepository,
)
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService

YEAR = 2025


def _purchase_factor(code: str, description: str | None) -> Factor:
    classification: dict = {"purchase_institutional_code": code}
    if description is not None:
        classification["purchase_institutional_description"] = description
    return Factor(
        emission_type_id=8,
        data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
        year=YEAR,
        classification=classification,
        values={},
    )


def _translation(value: str, label: str) -> ClassificationTranslation:
    return ClassificationTranslation(
        field_name="purchase_institutional_description",
        value=value,
        lang="fr",
        label=label,
    )


@pytest.mark.asyncio
async def test_upsert_inserts_then_updates_on_conflict(pg_session: AsyncSession):
    """Re-ingesting the same CSV must re-upsert, and a corrected `_fr` cell
    must overwrite the previous label — one row either way.
    """
    repo = ClassificationTranslationRepository(pg_session)

    await repo.upsert([_translation("Power tools", "Outils")])
    await pg_session.commit()
    await repo.upsert([_translation("Power tools", "Outils électriques")])
    await pg_session.commit()

    rows = (await pg_session.exec(select(ClassificationTranslation))).all()
    assert [(r.field_name, r.value, r.lang, r.label) for r in rows] == [
        (
            "purchase_institutional_description",
            "Power tools",
            "fr",
            "Outils électriques",
        )
    ]


@pytest.mark.asyncio
async def test_typeahead_search_on_real_postgres(pg_session: AsyncSession):
    """DISTINCT + relevance CASE ordering + JSONB ->> matching, end to end
    on Postgres: French term via the translation table, blank description
    falling back to the code, relevance tiers on the English text.
    """
    pg_session.add_all(
        [
            _purchase_factor("43211501", "Computer servers"),
            _purchase_factor("43211503", "Notebook computers"),
            _purchase_factor("27112700", "Power tools"),
            _purchase_factor("95121800", None),
            _translation("Power tools", "Outils électriques"),
        ]
    )
    await pg_session.commit()

    det = DataEntryTypeEnum.other_purchases
    handler = BaseModuleHandler.get_by_type(det)
    service = ModuleHandlerService(pg_session)

    english = await service.search_factor_options(
        handler, det, YEAR, "computer", "en", 20
    )
    assert [(o.name, o.label) for o in english] == [
        ("43211501", "Computer servers"),
        ("43211503", "Notebook computers"),
    ]

    french = await service.search_factor_options(
        handler, det, YEAR, "outils", "fr-CH", 20
    )
    assert [(o.name, o.label) for o in french] == [("27112700", "Outils électriques")]

    by_code = await service.search_factor_options(handler, det, YEAR, "9512", "en", 20)
    assert [(o.name, o.label) for o in by_code] == [("95121800", "95121800")]


@pytest.mark.asyncio
async def test_submodule_filter_and_row_labels_on_real_postgres(
    pg_session: AsyncSession,
):
    """The #2516 filter hop (`code IN (factor codes whose description
    matches)`) and the #2401 row `labels` map, against real JSONB.
    """
    # Real Postgres enforces the carbon_reports.unit_id FK (the sqlite
    # unit-suite twin gets away without a units row).
    unit = Unit(
        provider=UserProvider.TEST,
        institutional_code="U2401",
        name="Translation test unit",
        level=1,
        is_active=True,
    )
    pg_session.add(unit)
    await pg_session.flush()
    report = CarbonReport(year=YEAR, unit_id=unit.id, overall_status=0)
    pg_session.add(report)
    await pg_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.purchase.value,
        # asyncpg is strict about the integer status column (sqlite coerces).
        status=0,
    )
    pg_session.add(module)
    await pg_session.flush()
    pg_session.add_all(
        [
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.other_purchases,
                status=DataEntryStatusEnum.PENDING,
                data={
                    "name": "travel adapter",
                    "supplier": "supplier-1",
                    "quantity": 1,
                    "total_spent_amount": 10.0,
                    "currency": "chf",
                    "purchase_institutional_code": "27112700",
                },
                year=YEAR,
            ),
            DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.other_purchases,
                status=DataEntryStatusEnum.PENDING,
                data={
                    "name": "mounting strips",
                    "supplier": "supplier-1",
                    "quantity": 1,
                    "total_spent_amount": 10.0,
                    "currency": "chf",
                    "purchase_institutional_code": "44121600",
                },
                year=YEAR,
            ),
            _purchase_factor("27112700", "Power tools"),
            _purchase_factor("44121600", "Adhesives"),
            _translation("Power tools", "Outils électriques"),
        ]
    )
    await pg_session.commit()

    repo = DataEntryRepository(pg_session)
    response = await repo.get_submodule_data(
        carbon_report_module_id=module.id,
        data_entry_type_id=DataEntryTypeEnum.other_purchases.value,
        limit=100,
        offset=0,
        sort_by="id",
        sort_order="asc",
        filter="outils",
        lang="fr",
    )

    assert [item.purchase_institutional_code for item in response.items] == ["27112700"]
    assert response.items[0].labels == {
        "purchase_institutional_code": "Outils électriques"
    }
