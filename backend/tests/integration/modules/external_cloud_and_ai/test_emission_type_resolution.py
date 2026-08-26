"""Integration: every shipped provider category lands on its own leaf (#2252).

Drives the real emission pipeline against a DB session — factor bulk-fetch
(``FactorRepository``), classification matching (``FactorResolver``),
runtime leaf resolution (``resolve_ai`` / ``resolve_clouds``) and formula
computation (``DataEntryEmissionService.prepare_create``) — and asserts the
persisted ``data_entry_emissions`` rows.

Two contracts, one per data entry type:

1. Each of the seven product-name AI categories the re-uploaded CSVs carry
   ("Claude (Anthropic)", "ChatGPT (OpenAI)", …) resolves to its dedicated
   ``external__ai__provider_*`` leaf and matches the factor filed under the
   same spelling — with all seven factors present, so a mapping swap or a
   cross-provider factor match is falsifiable.
2. Each cloud ``service_type`` (virtualisation / compute / storage) resolves
   to its ``external__clouds__*`` leaf the same way.
"""

import pytest
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.services.data_entry_emission_service import DataEntryEmissionService

YEAR = 2025

# The seven product-name categories shipped by #2252 — same spellings as
# the factor/entry CSVs and the random seeders.
AI_PROVIDER_CASES: list[tuple[str, EmissionType]] = [
    ("Gemini (Google)", EmissionType.external__ai__provider_google),
    ("Mistral AI", EmissionType.external__ai__provider_mistral_ai),
    ("Claude (Anthropic)", EmissionType.external__ai__provider_anthropic),
    ("ChatGPT (OpenAI)", EmissionType.external__ai__provider_openai),
    ("Copilot (Microsoft)", EmissionType.external__ai__provider_microsoft),
    ("Copilot (GitHub)", EmissionType.external__ai__provider_github),
    ("Other", EmissionType.external__ai__provider_others),
]

CLOUD_SERVICE_CASES: list[tuple[str, EmissionType]] = [
    ("virtualisation", EmissionType.external__clouds__virtualisation),
    ("compute", EmissionType.external__clouds__calcul),
    ("storage", EmissionType.external__clouds__stockage),
]


async def _seed_module(
    db_session: AsyncSession, make_carbon_report, make_carbon_report_module
):
    report = await make_carbon_report(db_session, year=YEAR)
    return await make_carbon_report_module(
        db_session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.external_cloud_and_ai.value,
    )


async def _persisted_emissions_by_entry(
    db_session: AsyncSession, entry_ids: list[int]
) -> dict[int, list[DataEntryEmission]]:
    result = await db_session.execute(
        select(DataEntryEmission).where(
            col(DataEntryEmission.data_entry_id).in_(entry_ids)
        )
    )
    emissions_by_entry: dict[int, list[DataEntryEmission]] = {}
    for emission in result.scalars().all():
        emissions_by_entry.setdefault(emission.data_entry_id, []).append(emission)
    return emissions_by_entry


async def _create_and_persist_emissions(
    db_session: AsyncSession, entries: list[DataEntry]
) -> None:
    service = DataEntryEmissionService(db_session)
    for entry in entries:
        rows = await service.prepare_create(entry)
        await service.repo.bulk_create([row.to_orm() for row in rows])
    await db_session.commit()


@pytest.mark.asyncio
async def test_each_ai_provider_category_resolves_to_its_emission_type(
    db_session: AsyncSession,
    make_carbon_report,
    make_carbon_report_module,
    make_factor,
    make_data_entry,
):
    module = await _seed_module(
        db_session, make_carbon_report, make_carbon_report_module
    )

    factor_ids: dict[str, int] = {}
    for provider, expected in AI_PROVIDER_CASES:
        factor = await make_factor(
            db_session,
            emission_type_id=expected.value,
            data_entry_type_id=DataEntryTypeEnum.external_ai.value,
            classification={"provider": provider, "usage_type": "text"},
            values={"ef_kg_co2eq_per_request": 0.005},
            year=YEAR,
        )
        factor_ids[provider] = factor.id

    entries: dict[str, DataEntry] = {}
    for provider, _ in AI_PROVIDER_CASES:
        entries[provider] = await make_data_entry(
            db_session,
            data_entry_type_id=DataEntryTypeEnum.external_ai.value,
            carbon_report_module_id=module.id,
            data={
                "provider": provider,
                "usage_type": "text",
                "requests_per_user_per_day": "1_5",
                "fte_count": 1.0,
            },
        )
    await db_session.commit()

    await _create_and_persist_emissions(db_session, list(entries.values()))

    emissions_by_entry = await _persisted_emissions_by_entry(
        db_session, [e.id for e in entries.values()]
    )
    for provider, expected in AI_PROVIDER_CASES:
        entry = entries[provider]
        rows = emissions_by_entry.get(entry.id, [])
        assert len(rows) == 1, (
            f"provider {provider!r}: expected exactly one emission row, "
            f"got {[(r.emission_type_id, r.kg_co2eq) for r in rows]}"
        )
        row = rows[0]
        assert row.emission_type_id == expected.value, (
            f"provider {provider!r} resolved to emission_type_id="
            f"{row.emission_type_id} ({EmissionType(row.emission_type_id).name}), "
            f"expected {expected.value} ({expected.name})"
        )
        assert row.primary_factor_id == factor_ids[provider], (
            f"provider {provider!r} matched factor id={row.primary_factor_id}, "
            f"expected its own factor id={factor_ids[provider]}"
        )


@pytest.mark.asyncio
async def test_each_cloud_service_type_resolves_to_its_emission_type(
    db_session: AsyncSession,
    make_carbon_report,
    make_carbon_report_module,
    make_factor,
    make_data_entry,
):
    module = await _seed_module(
        db_session, make_carbon_report, make_carbon_report_module
    )

    factor_ids: dict[str, int] = {}
    for service_type, expected in CLOUD_SERVICE_CASES:
        factor = await make_factor(
            db_session,
            emission_type_id=expected.value,
            data_entry_type_id=DataEntryTypeEnum.external_clouds.value,
            classification={
                "provider": "AWS",
                "service_type": service_type,
                "currency": "eur",
            },
            values={"ef_kg_co2eq_per_currency": 0.05, "currency": "eur"},
            year=YEAR,
        )
        factor_ids[service_type] = factor.id

    entries: dict[str, DataEntry] = {}
    for service_type, _ in CLOUD_SERVICE_CASES:
        entries[service_type] = await make_data_entry(
            db_session,
            data_entry_type_id=DataEntryTypeEnum.external_clouds.value,
            carbon_report_module_id=module.id,
            data={
                "provider": "AWS",
                "service_type": service_type,
                "spent_amount": 100.0,
                "currency": "eur",
            },
        )
    await db_session.commit()

    await _create_and_persist_emissions(db_session, list(entries.values()))

    emissions_by_entry = await _persisted_emissions_by_entry(
        db_session, [e.id for e in entries.values()]
    )
    for service_type, expected in CLOUD_SERVICE_CASES:
        entry = entries[service_type]
        rows = emissions_by_entry.get(entry.id, [])
        assert len(rows) == 1, (
            f"service_type {service_type!r}: expected exactly one emission row, "
            f"got {[(r.emission_type_id, r.kg_co2eq) for r in rows]}"
        )
        row = rows[0]
        assert row.emission_type_id == expected.value, (
            f"service_type {service_type!r} resolved to emission_type_id="
            f"{row.emission_type_id} ({EmissionType(row.emission_type_id).name}), "
            f"expected {expected.value} ({expected.name})"
        )
        assert row.primary_factor_id == factor_ids[service_type], (
            f"service_type {service_type!r} matched factor "
            f"id={row.primary_factor_id}, expected its own factor "
            f"id={factor_ids[service_type]}"
        )
