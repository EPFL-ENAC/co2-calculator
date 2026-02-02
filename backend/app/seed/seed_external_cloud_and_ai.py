import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum
from app.models.module_type import ModuleTypeEnum

# from app.models.emission_type import EmissionTypeEnum
from app.seed.seed_helper import (
    get_carbon_report_module_id,
    load_factors_map,
    lookup_factor,
    normalize_kind,
)
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.factor_service import FactorService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT


CSV_PATH_EXTERNAL_CLOUDS = (
    Path(__file__).parent.parent.parent / "seed_data" / "seed_external_clouds_data.csv"
)

CSV_PATH_EXTERNAL_AI = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_external_clouds_ai_data.csv"
)


CSV_PATH_EXTERNAL_CLOUDS_FACTOR = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_external_clouds_factors.csv"
)

CSV_PATH_EXTERNAL_AI_FACTOR = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_external_clouds_ai_factors.csv"
)


# OUTPUT # Provider | Service Type | Spending (€) | kg CO₂-eq
# INPUT # Service Type | Provider | Spending
# RENAMING COLUMNS
# -> Service Type  -> service_type
# -> Provider      -> cloud_provider
# -> Spending (€)  -> spending
async def seed_data_clouds(session: AsyncSession, carbon_report_module_id: int) -> None:
    """Seed External Cloud and AI data entries."""
    service = DataEntryService(session)
    data_entries = []
    #  bulk delete data entries
    await service.bulk_delete(
        carbon_report_module_id, DataEntryTypeEnum.external_clouds
    )

    factors_map = await load_factors_map(session, DataEntryTypeEnum.external_clouds)

    with open(CSV_PATH_EXTERNAL_CLOUDS, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            kind = normalize_kind(row.get("cloud_provider", ""))
            subkind = normalize_kind(row.get("service_type", ""))
            factor = lookup_factor(kind, subkind, factors_map)
            data_entry = DataEntry(
                carbon_report_module_id=carbon_report_module_id,
                data={
                    "primary_factor_id": factor.id if factor else None,
                    "spending": float(row.get("spending", 0)),
                    "service_type": (row.get("service_type") or "").lower(),
                    "cloud_provider": (row.get("cloud_provider") or "").lower(),
                },
            )
            data_entry.data_entry_type = DataEntryTypeEnum.external_clouds
            data_entries.append(data_entry)
    # 1. Bulk create all data entries first
    data_entries_response = await service.bulk_create(data_entries)
    # 2. Now, create the emissions for all of them using the service logic
    print(f"Created {len(data_entries_response)} External Cloud data entries")
    emissions_to_create = []
    emission_service = DataEntryEmissionService(session)

    for data_entry_response in data_entries_response:
        # Use a method that PREPARES the model but doesn't commit yet
        # service_type is stored in lower case in the CSV?
        emission_obj = await emission_service.prepare_create(data_entry_response)
        if emission_obj is not None:
            emissions_to_create.append(emission_obj)

    # 3. Bulk create the emissions
    print(f"Creating {len(emissions_to_create)} emissions for cloud data entries")
    await emission_service.bulk_create(emissions_to_create)

    # # 4. ONE final commit for the entire seed batch

    await session.commit()
    logger.info("Seeded External Cloud data entries.")


# input: Provider | Use | Number of users | Frequency (time/day)
async def seed_data_ai(session: AsyncSession, carbon_report_module_id: int) -> None:
    """Seed External AI data entries."""
    service = DataEntryService(session)
    data_entries = []
    await service.bulk_delete(carbon_report_module_id, DataEntryTypeEnum.external_ai)

    factors_map = await load_factors_map(session, DataEntryTypeEnum.external_ai)
    with open(CSV_PATH_EXTERNAL_AI, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            kind = normalize_kind(row.get("ai_provider", ""))
            subkind = normalize_kind(row.get("ai_use", ""))
            factor = lookup_factor(kind, subkind, factors_map)
            data_entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.external_ai,
                carbon_report_module_id=carbon_report_module_id,
                data={
                    "primary_factor_id": factor.id if factor else None,
                    "frequency_use_per_day": int(row.get("frequency_use_per_day", 0)),
                    "user_count": int(row.get("user_count", 0)),
                    "ai_provider": (row.get("ai_provider") or "").lower(),
                    "ai_use": (row.get("ai_use") or "").lower(),
                },
            )
            data_entries.append(data_entry)
    # 1. Bulk create all data entries first
    data_entries_response = await service.bulk_create(data_entries)
    # 2. Now, create the emissions for all of them using the service logic
    print(f"Created {len(data_entries_response)} External AI data entries")
    emissions_to_create = []
    emission_service = DataEntryEmissionService(session)

    for data_entry_response in data_entries_response:
        # Use a method that PREPARES the model but doesn't commit yet
        # service_type is stored in lower case in the CSV?
        emission_obj = await emission_service.prepare_create(data_entry_response)
        if emission_obj is not None:
            emissions_to_create.append(emission_obj)

    # 3. Bulk create the emissions
    print(f"Creating {len(emissions_to_create)} emissions for ai data entries")
    await emission_service.bulk_create(emissions_to_create)

    # # 4. ONE final commit for the entire seed batch

    await session.commit()
    logger.info("Seeded External AI data entries.")


def get_float_or_none(value: str | None) -> float | None:
    """Convert string to float or return None if empty."""
    if value is None:
        return None

    if value == "":
        return None
    return float(value)


async def seed_factor_clouds(session: AsyncSession) -> None:
    """Seed factors for External Cloud.
    1. bulk delete factors
    2. bulk insert factors
    """
    service = FactorService(session)
    factors = []
    # 1. bulk delete factors
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.external_clouds)
    with open(CSV_PATH_EXTERNAL_CLOUDS_FACTOR, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            #  for cloud emission_type depends on service_type

            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum[
                    (row.get("service_type") or "").lower()
                ],
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.external_clouds,
                classification={
                    "cloud_provider": (row.get("cloud_provider") or "").lower(),
                    "service_type": (row.get("service_type") or "").lower(),
                    "kind": (row.get("cloud_provider") or "").lower(),
                    "subkind": (row.get("service_type") or "").lower(),
                },
                values={
                    "factor_kgco2_per_eur": get_float_or_none(
                        row.get("factor_kgco2_per_eur")
                    ),
                },
            )
            factors.append(factor)
    await service.bulk_create(factors)
    print(f"Created {len(factors)} External Cloud factors")
    await session.commit()
    logger.info("Seeded External Cloud factors.")


async def seed_factor_ai(session: AsyncSession) -> None:
    """Seed factors for External AI.
    1. bulk delete factors
    2. bulk insert factors
    """
    service = FactorService(session)
    factors = []
    # 1. bulk delete factors
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.external_ai)
    with open(CSV_PATH_EXTERNAL_AI_FACTOR, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            #  for cloud emission_type depends on service_type
            factor_gCO2eq = get_float_or_none(row.get("factor_gCO2eq"))
            if factor_gCO2eq is None:
                # // skip rows without factor
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum.ai_provider,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.external_ai.value,
                # TODO: unify data model with kind/subkind so
                # it corresponds to ai_provider/ai_use?
                classification={
                    "ai_provider": (row.get("ai_provider") or "").lower(),
                    "ai_use": (row.get("ai_use") or "").lower(),
                    "kind": (row.get("ai_provider") or "").lower(),
                    "subkind": (row.get("ai_use") or "").lower(),
                },
                values={
                    "factor_gCO2eq": factor_gCO2eq,
                },
            )
            factors.append(factor)
    await service.bulk_create(factors)
    print(f"Created {len(factors)} External AI factors")
    await session.commit()
    logger.info("Seeded External AI factors.")


async def main() -> None:
    """Main seed function."""

    async with SessionLocal() as session:
        # // clean emissions first
        await seed_factor_clouds(session)
        await seed_factor_ai(session)
        # Seed for unit provider code 10208 and 12345 for year 2025
        # DATA and EMISSIONS
        carbon_report_module_id_10208 = await get_carbon_report_module_id(
            unit_provider_code="10208",
            year=2025,
            module_type_id=ModuleTypeEnum.external_cloud_and_ai,
        )
        # await seed_data_clouds(session, carbon_report_module_id_10208)
        await seed_data_ai(session, carbon_report_module_id_10208)

        carbon_report_module_id_12345 = await get_carbon_report_module_id(
            unit_provider_code="12345",
            year=2025,
            module_type_id=ModuleTypeEnum.external_cloud_and_ai,
        )
        await seed_data_clouds(session, carbon_report_module_id_12345)
        await seed_data_ai(session, carbon_report_module_id_12345)


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
