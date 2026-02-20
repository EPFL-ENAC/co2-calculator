"""Seed building energy kWh/m² factors and combustion factors from CSV."""

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

CSV_PATH_BUILDING_ENERGY = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_building_energy_factors.csv"
)

CSV_PATH_COMBUSTION = (
    Path(__file__).parent.parent.parent / "seed_data" / "seed_combustion_factors.csv"
)


def _float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


async def seed_building_energy_factors(session: AsyncSession) -> None:
    """Seed kWh/m² factors for each SIA room type."""
    service = FactorService(session)
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.building)

    factors = []
    with open(CSV_PATH_BUILDING_ENERGY, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            heating = _float_or_none(row.get("heating_kwh_per_m2"))
            if heating is None:
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum.energy,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                classification={
                    "kind": row.get("kind", ""),
                    "subkind": row.get("subkind") or None,
                    "source": row.get("source", ""),
                },
                values={
                    "heating_kwh_per_m2": heating,
                    "cooling_kwh_per_m2": _float_or_none(row.get("cooling_kwh_per_m2")),
                    "ventilation_kwh_per_m2": _float_or_none(
                        row.get("ventilation_kwh_per_m2")
                    ),
                    "lighting_kwh_per_m2": _float_or_none(
                        row.get("lighting_kwh_per_m2")
                    ),
                },
            )
            factors.append(factor)

    await service.bulk_create(factors)
    await session.commit()
    logger.info(f"Seeded {len(factors)} building energy factors.")


async def seed_combustion_factors(session: AsyncSession) -> None:
    """Seed kg CO₂-eq per unit factors for combustion heating types."""
    service = FactorService(session)
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.energy_combustion)

    factors = []
    with open(CSV_PATH_COMBUSTION, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            kgco2 = _float_or_none(row.get("kg_co2eq_per_unit"))
            if kgco2 is None:
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum.combustion,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
                classification={
                    "kind": row.get("kind", ""),
                    "subkind": row.get("subkind") or None,
                    "source": row.get("source", ""),
                },
                values={
                    "kg_co2eq_per_unit": kgco2,
                    "unit": row.get("unit", ""),
                },
            )
            factors.append(factor)

    await service.bulk_create(factors)
    await session.commit()
    logger.info(f"Seeded {len(factors)} combustion factors.")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_building_energy_factors(session)
        await seed_combustion_factors(session)


if __name__ == "__main__":
    asyncio.run(main())
