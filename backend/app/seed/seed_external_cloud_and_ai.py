import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.seed.seed_helper import get_carbon_report_module_id
from app.services.data_entry_service import DataEntryService

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
    await service.bulk_delete(
        carbon_report_module_id, DataEntryTypeEnum.external_clouds
    )

    with open(CSV_PATH_EXTERNAL_CLOUDS, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data_entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.external_clouds,
                carbon_report_module_id=carbon_report_module_id,
                data={
                    "cloud_provider": row.get("cloud_provider"),
                    "service_type": row.get("service_type"),
                    "spending": float(row.get("spending", 0)),
                    "region": row.get("region"),
                },
            )
            data_entries.append(data_entry)
    await service.bulk_create(data_entries)
    logger.info("Seeded External Cloud data entries.")


# input: Provider | Use | Number of users | Frequency (time/day)
async def seed_data_ai(session: AsyncSession, carbon_report_module_id: int) -> None:
    """Seed External AI data entries."""
    service = DataEntryService(session)
    data_entries = []
    await service.bulk_delete(carbon_report_module_id, DataEntryTypeEnum.external_ai)
    with open(CSV_PATH_EXTERNAL_AI, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            print(row)
            data_entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.external_ai,
                carbon_report_module_id=carbon_report_module_id,
                data={
                    "ai_provider": row.get("ai_provider"),
                    "ai_use": row.get("ai_use"),
                    "frequency_use_per_day": int(row.get("frequency_use_per_day", 0)),
                    "user_count": int(row.get("user_count", 0)),
                },
            )
            data_entries.append(data_entry)
    await service.bulk_create(data_entries)
    logger.info("Seeded External AI data entries.")


async def main() -> None:
    """Main seed function."""

    async with SessionLocal() as session:
        carbon_report_module_id_10208 = await get_carbon_report_module_id(
            unit_provider_code="10208", year=2025
        )
        await seed_data_clouds(session, carbon_report_module_id_10208)
        await seed_data_ai(session, carbon_report_module_id_10208)

        carbon_report_module_id_12345 = await get_carbon_report_module_id(
            unit_provider_code="12345", year=2025
        )
        await seed_data_clouds(session, carbon_report_module_id_12345)
        await seed_data_ai(session, carbon_report_module_id_12345)


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
