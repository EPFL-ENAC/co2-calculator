"""Seed professional travel factors from CSV data.

This script populates the factors table with professional travel impact factors
(plane and train) using the generic Factor model, following the same pattern
as seed_external_cloud_and_ai.py.
"""

import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum
from app.services.factor_service import FactorService

logger = get_logger(__name__)

CSV_PATH_FACTORS = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_professional_travel_factors.csv"
)


def get_float_or_none(value: str | None) -> float | None:
    """Convert string to float or return None if empty."""
    if value is None or value == "":
        return None
    return float(value)


async def seed_professional_travel_factors(session: AsyncSession) -> None:
    """Seed factors for professional travel (plane and train).

    Uses the generic Factor model with:
    - emission_type_id: flight (7) or train (8)
    - data_entry_type_id: trips
    - classification: transport_mode, category (for plane), countrycode (for train)
    - values: impact_score, rfi_adjustment, min_distance, max_distance
    """
    service = FactorService(session)
    factors = []

    # 1. bulk delete existing professional travel factors
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.trips)

    if not CSV_PATH_FACTORS.exists():
        logger.error(f"CSV file not found: {CSV_PATH_FACTORS}")
        return

    with open(CSV_PATH_FACTORS, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row_num, row in enumerate(reader, start=2):
            try:
                transport_mode = row.get("transport_mode", "").strip()
                if not transport_mode:
                    logger.warning(f"Row {row_num}: Missing transport_mode, skipping")
                    continue

                # Determine emission type based on transport mode
                if transport_mode == "flight":
                    emission_type = EmissionTypeEnum.flight
                elif transport_mode == "train":
                    emission_type = EmissionTypeEnum.train
                else:
                    logger.warning(
                        f"Row {row_num}: Unknown transport_mode '{transport_mode}', "
                        "skipping"
                    )
                    continue

                # Parse values
                impact_score = get_float_or_none(row.get("impact_score"))
                if impact_score is None:
                    logger.warning(f"Row {row_num}: Missing impact_score, skipping")
                    continue

                rfi_adjustment = get_float_or_none(row.get("rfi_adjustment"))
                min_distance = get_float_or_none(row.get("min_distance"))
                max_distance = get_float_or_none(row.get("max_distance"))

                # Build classification based on transport mode
                classification = {
                    "transport_mode": transport_mode,
                    "kind": transport_mode,  # For lookup compatibility
                }

                if transport_mode == "flight":
                    category = row.get("category", "").strip()
                    if category:
                        classification["category"] = category
                        classification["subkind"] = category  # For lookup compatibility
                elif transport_mode == "train":
                    countrycode = row.get("countrycode", "").strip()
                    if countrycode:
                        classification["countrycode"] = countrycode
                        classification["subkind"] = countrycode  # For lookup

                # Build values dict
                values: dict[str, float | int | None] = {
                    "impact_score": impact_score,
                }
                if rfi_adjustment is not None:
                    values["rfi_adjustment"] = rfi_adjustment
                if min_distance is not None:
                    values["min_distance"] = min_distance
                if max_distance is not None:
                    values["max_distance"] = max_distance

                # Prepare factor using service
                factor = await service.prepare_create(
                    emission_type_id=emission_type.value,
                    is_conversion=False,
                    data_entry_type_id=DataEntryTypeEnum.trips.value,
                    classification=classification,
                    values=values,
                )
                factors.append(factor)
                subkind = classification.get("category") or classification.get(
                    "countrycode"
                )
                logger.debug(f"Prepared factor: {transport_mode} {subkind}")

            except Exception as e:
                logger.error(f"Row {row_num}: Error processing row: {e}")
                continue

    # Bulk create all factors
    if factors:
        await service.bulk_create(factors)
        logger.info(f"Created {len(factors)} professional travel factors")

    await session.commit()
    logger.info("Seeded professional travel factors.")


async def main() -> None:
    """Main seed function."""
    logger.info("Starting professional travel factors seeding...")

    async with SessionLocal() as session:
        await seed_professional_travel_factors(session)

    logger.info("Professional travel factors seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
