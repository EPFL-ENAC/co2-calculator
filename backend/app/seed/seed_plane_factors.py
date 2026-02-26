"""Seed plane/flight impact factors from CSV."""

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
    / "seed_travel_plane_impact_factors.csv"
)


async def seed_plane_factors() -> None:
    """Seed flight impact factors."""
    async with SessionLocal() as session:
        service = FactorService(session)

        # Delete existing flight factors
        existing = await service.list_by_data_entry_type(DataEntryTypeEnum.plane)
        ids = [
            f.id
            for f in existing
            if f.emission_type_id == EmissionTypeEnum.plane.value and f.id
        ]
        if ids:
            await service.bulk_delete(ids)

        # Load and create factors from CSV
        factors = []
        with open(CSV_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                category = row["category"]
                impact_score_raw = row.get("impact_score") or row.get(
                    "ef_kg_co2eq_per_km"
                )
                rfi_adjustment_raw = row.get("rfi_adjustment") or row.get(
                    "rfi_adjustement"
                )
                factor = await service.prepare_create(
                    emission_type_id=EmissionTypeEnum.plane.value,
                    is_conversion=False,
                    data_entry_type_id=DataEntryTypeEnum.plane.value,
                    classification={
                        "kind": TransportModeEnum.plane.value,
                        "subkind": category,
                        "category": category,
                    },
                    values={
                        # Keep both key variants for backward compatibility.
                        "impact_score": float(impact_score_raw)
                        if impact_score_raw
                        else None,
                        "ef_kg_co2eq_per_km": float(impact_score_raw)
                        if impact_score_raw
                        else None,
                        "rfi_adjustment": float(rfi_adjustment_raw)
                        if rfi_adjustment_raw
                        else None,
                        "rfi_adjustement": float(rfi_adjustment_raw)
                        if rfi_adjustment_raw
                        else None,
                        "min_distance": float(row["min_distance"])
                        if row.get("min_distance")
                        else None,
                        "max_distance": float(row["max_distance"])
                        if row.get("max_distance")
                        else None,
                    },
                )
                factors.append(factor)

        await service.bulk_create(factors)
        await session.commit()
        logger.info(f"Seeded {len(factors)} plane impact factors")


if __name__ == "__main__":
    asyncio.run(seed_plane_factors())
