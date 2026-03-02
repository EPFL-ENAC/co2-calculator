"""Seed train impact factors from CSV."""

import asyncio
import csv
from pathlib import Path

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.modules.headcount import (
    schemas as schemas,
)  # This ensures the handlers are registered
from app.services.factor_service import FactorService

logger = get_logger(__name__)
CSV_PATH = (
    Path(__file__).parent.parent.parent / "seed_data" / "seed_headcount_factors.csv"
)


async def seed_headcount_factors() -> None:
    """Seed headcount impact factors."""
    async with SessionLocal() as session:
        service = FactorService(session)

        # Delete existing headcount factors
        # existing = await service.list_id_by_data_entry_type(DataEntryTypeEnum.member)

        # if ids:
        #     await service.bulk_delete(ids)

        # Load and create factors from CSV
        factors = []
        with open(CSV_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ef_kg_co2eq_per_fte = row.get("ef_kg_co2eq_per_fte")

                type = row["type"]
                category = row["category"]
                sub_category = row["sub_category"]

                ef_kg_co2eq_per_fte

                factor = await service.prepare_create(
                    emission_type_id=EmissionType[type].value,
                    is_conversion=False,
                    data_entry_type_id=DataEntryTypeEnum.member.value,
                    classification={
                        "kind": category,
                        "subkind": sub_category,
                        "type": type,
                    },
                    values={
                        "ef_kg_co2eq_per_fte": float(ef_kg_co2eq_per_fte)
                        if ef_kg_co2eq_per_fte
                        else None,
                    },
                )
                factors.append(factor)

        await service.bulk_create(factors)
        await session.commit()
        logger.info(f"Seeded {len(factors)} headcount impact factors")


if __name__ == "__main__":
    asyncio.run(seed_headcount_factors())
