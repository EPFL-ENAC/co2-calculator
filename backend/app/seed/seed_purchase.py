import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionTypeEnum
from app.services.factor_service import FactorService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT

CSV_PATH_COMMON_FACTOR = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_purchase_common_factors.csv"
)


def get_float_or_none(value: str | None) -> float | None:
    """Convert string to float or return None if empty."""
    if value is None:
        return None

    if value == "":
        return None
    return float(value)


async def seed_factor_by_entry_type(session: AsyncSession, entry_type: str) -> None:
    """Seed factors for External Cloud.
    1. bulk delete factors
    2. bulk insert factors
    """
    service = FactorService(session)
    factors = []
    # 1. bulk delete factors
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum[entry_type])
    with open(CSV_PATH_COMMON_FACTOR, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            purchase_category = row.get("purchase_category", "")
            if (
                purchase_category == ""
                or purchase_category.lower() != entry_type.lower()
            ):
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum[f"purchase_{entry_type}"],
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum[entry_type],
                classification={
                    "purchase_institutional_code": row.get(
                        "purchase_institutional_code", ""
                    ),
                    "purchase_category": row.get("purchase_category", ""),
                    "kind": row.get("purchase_institutional_code", ""),
                },
                values={
                    "currency": row.get("currency", "eur").lower(),
                    "ef_kg_co2eq_per_currency": get_float_or_none(
                        row.get("ef_kg_co2eq_per_currency")
                    ),
                },
            )
            factors.append(factor)
    await service.bulk_create(factors)
    print(f"Created {len(factors)} Purchase Common factors")
    await session.commit()
    logger.info("Seeded Purchase Common factors.")


async def main():
    logger.info("Starting purchase data seeding...")

    async with SessionLocal() as session:
        await seed_factor_by_entry_type(session, "scientific_equipment")
        await session.commit()
        await seed_factor_by_entry_type(session, "it_equipment")
        await session.commit()
        await seed_factor_by_entry_type(session, "consumable_accessories")
        await session.commit()
        await seed_factor_by_entry_type(session, "biological_chemical_gaseous_product")
        await session.commit()
        await seed_factor_by_entry_type(session, "services")
        await session.commit()
        await seed_factor_by_entry_type(session, "vehicles")
        await session.commit()
        await seed_factor_by_entry_type(session, "other_purchases")
        await session.commit()

    logger.info("Purchase data seeding completed.")


if __name__ == "__main__":
    asyncio.run(main())
