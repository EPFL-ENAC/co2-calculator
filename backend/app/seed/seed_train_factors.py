"""Seed train impact factors from CSV."""

import asyncio
import csv
from pathlib import Path

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionTypeEnum
from app.models.location import TransportModeEnum
from app.modules.professional_travel import (
    schemas as schemas,
)  # This ensures the handlers are registered
from app.services.factor_service import FactorService

logger = get_logger(__name__)
CSV_PATH = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_travel_train_impact_factors.csv"
)


async def seed_train_factors() -> None:
    """Seed train impact factors."""
    async with SessionLocal() as session:
        service = FactorService(session)

        # Delete existing train factors
        existing = await service.list_by_data_entry_type(DataEntryTypeEnum.train)
        ids = [
            f.id
            for f in existing
            if f.emission_type_id == EmissionTypeEnum.train.value and f.id
        ]
        if ids:
            await service.bulk_delete(ids)

        # Load and create factors from CSV
        factors = []
        with open(CSV_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                country_code = row["country_code"]
                impact_score_raw = row.get("impact_score") or row.get(
                    "ef_kg_co2eq_per_km"
                )
                factor = await service.prepare_create(
                    emission_type_id=EmissionTypeEnum.train.value,
                    is_conversion=False,
                    data_entry_type_id=DataEntryTypeEnum.train.value,
                    classification={
                        "kind": TransportModeEnum.train.value,
                        "subkind": country_code,
                        "country_code": country_code,
                    },
                    values={
                        # Keep both key variants for backward compatibility.
                        "impact_score": float(impact_score_raw)
                        if impact_score_raw
                        else None,
                        "ef_kg_co2eq_per_km": float(impact_score_raw)
                        if impact_score_raw
                        else None,
                    },
                )
                factors.append(factor)

        await service.bulk_create(factors)
        await session.commit()
        logger.info(f"Seeded {len(factors)} train impact factors")


if __name__ == "__main__":
    asyncio.run(seed_train_factors())
