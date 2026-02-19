"""Seed processes GWP factors from CSV (IPCC AR6 2021 + labo1point5)."""

import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionTypeEnum
from app.services.factor_service import FactorService

logger = get_logger(__name__)

CSV_PATH_PROCESS_EMISSIONS_FACTORS = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_process_emissions_factors.csv"
)


def get_float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


async def seed_process_emissions_factors(session: AsyncSession) -> None:
    """Seed GWP factors for processes module from CSV into the factors table."""
    service = FactorService(session)
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.process_emissions)

    factors = []
    with open(CSV_PATH_PROCESS_EMISSIONS_FACTORS, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            gwp = get_float_or_none(row.get("gwp_kg_co2eq_per_kg"))
            if gwp is None:
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum.process_emissions,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
                classification={
                    "kind": row.get("kind", ""),
                    "subkind": row.get("subkind") or None,
                    "source": row.get("source", ""),
                },
                values={
                    "gwp_kg_co2eq_per_kg": gwp,
                },
            )
            factors.append(factor)

    await service.bulk_create(factors)
    await session.commit()
    logger.info(f"Seeded {len(factors)} process emissions factors.")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_process_emissions_factors(session)


if __name__ == "__main__":
    asyncio.run(main())
