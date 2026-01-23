"""Seed emission factors and power factors from CSV data.

This script populates the emission_factors and power_factors tables with initial data:
- Swiss electricity mix emission factor (from config)
- Power consumption factors from table_power.csv
"""

import asyncio
import csv
from datetime import datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry_type import DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum

# from app.models.emission_factor import EmissionFactor, PowerFactor
from app.models.factor import Factor

logger = get_logger(__name__)
settings = get_settings()

CSV_PATH = (
    Path(__file__).parent.parent.parent / "seed_data" / "seed_equipment_table_power.csv"
)


async def seed_emission_factors(session: AsyncSession) -> None:
    """Seed initial emission factors."""
    logger.info("Seeding emission factors...")

    # Check if Swiss mix factor already exists
    result = await session.exec(
        select(Factor).where(Factor.emission_type_id == EmissionTypeEnum.energy)
    )
    existing = result.first()

    if existing:
        logger.info("Swiss electricity mix emission factor already exists, skipping")
        return

    # Create Swiss electricity mix emission factor
    factor = Factor(
        emission_type_id=EmissionTypeEnum.energy,  # energy
        is_conversion=True,
        data_entry_type_id=DataEntryTypeEnum.energy_mix,
        classification={
            "region": "Switzerland",
            "source": "Swiss Federal Office of Energy (SFOE)",
            "unit": "kgCO2eq/kWh",
            "description": "Swiss electricity consumption mix",
            "methodology": "Life cycle analysis",
        },
        values={"kgco2eq_per_kwh": settings.EMISSION_FACTOR_SWISS_MIX},
    )

    session.add(factor)
    await session.commit()
    logger.info(
        f"Created emission factor: {factor.classification['description']} = {factor.values['kgco2eq_per_kwh']} kgCO2eq/kWh"
    )


async def seed_power_factors(session: AsyncSession) -> None:
    """Seed power factors from table_power.csv."""
    logger.info("Seeding power factors from CSV...")

    # Check if power factors already exist
    result = await session.exec(
        select(Factor).where(Factor.emission_type_id == EmissionTypeEnum.equipment)
    )
    existing = result.first()

    if existing:
        logger.info("Power factors already exist, skipping")
        return

    # Find the CSV file
    csv_path = CSV_PATH
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    # Read and parse CSV
    power_factors = []
    current_submodule = None
    # current_sub_category = None

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Track submodule and sub-category (they persist across rows when empty)
            submodule_val = row.get("Submodule", "").strip()
            if submodule_val:
                current_submodule = submodule_val

            # sub_category_val = row.get("Sub-category", "").strip()
            # if sub_category_val:
            #     current_sub_category = sub_category_val

            # Get class and sub-class
            equipment_class = row.get("Class", "").strip()
            sub_class = row.get("Sub-class", "").strip()

            # Skip if no class defined
            if not equipment_class:
                continue

            # Parse power values
            try:
                active_power = float(
                    row.get("Average power --Active mode (W)", "0") or "0"
                )
                standby_power = float(
                    row.get("Average power --Stand-by mode (W)", "0") or "0"
                )
            except ValueError:
                logger.warning(f"Invalid power values in row: {row}")
                continue

            power_factor = Factor(
                emission_type_id=EmissionTypeEnum.equipment,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum[
                    current_submodule or "other"
                ].value,
                classification={
                    "class": equipment_class,
                    "sub_class": sub_class or None,
                    "unit": "W",
                    "description": f"Power factor for {equipment_class}",
                },
                values={
                    "active_power_w": active_power,
                    "standby_power_w": standby_power,
                },
            )
            power_factors.append(power_factor)

    # Bulk insert
    session.add_all(power_factors)
    await session.commit()
    logger.info(f"Created {len(power_factors)} power factors from CSV")


async def main() -> None:
    """Main seed function."""
    logger.info("Starting emission factors seeding...")

    async with SessionLocal() as session:
        await seed_emission_factors(session)
        await seed_power_factors(session)

    logger.info("Emission factors seeding complete!")


if __name__ == "__main__":
    # run script on /app/api/v1/table_power.csv
    asyncio.run(main())
