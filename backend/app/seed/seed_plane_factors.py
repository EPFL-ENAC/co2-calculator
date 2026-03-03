"""Seed plane/flight impact factors from CSV."""

import asyncio
import csv
from pathlib import Path

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor
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

        def match_plane_emission_type(factor: Factor) -> bool:
            if not factor.emission_type_id:
                return False
            return factor.emission_type_id in {EmissionType.professional_travel__plane}

        ids = [
            f.id for f in existing if match_plane_emission_type(f) if f.id is not None
        ]
        if len(ids) > 0:
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
                    # no need to dynamically resolve the emission type
                    # since it's not dependent on the factor but the cabin_class data of
                    # the data_entry, and all rows in the CSV are for plane factors
                    # we'll just need to make sure the data_entry handler correctly
                    # assigns the emission type
                    emission_type_id=EmissionType.professional_travel__plane,
                    is_conversion=False,
                    data_entry_type_id=DataEntryTypeEnum.plane.value,
                    classification={
                        "kind": category,
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
