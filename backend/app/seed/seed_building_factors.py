"""Seed building energy and combustion factors from CSV."""

import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.seed.seed_helper import get_factor_emission_type_id
from app.services.factor_service import FactorService

logger = get_logger(__name__)

CSV_PATH_BUILDING_ENERGY = (
    Path(__file__).parent.parent.parent / "seed_data" / "building_rooms_factors.csv"
)

CSV_PATH_COMBUSTION = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "building_energycombustions_factors.csv"
)


def _float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _normalize_room_type(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value == "miscels":
        return "miscellaneous"
    return value


def _normalize_energy_type(raw: str | None) -> str:
    return (raw or "").strip().lower()


async def seed_building_energy_factors(session: AsyncSession) -> None:
    """Seed building energy factors from normalized building/category CSV."""
    service = FactorService(session)
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.building)

    factors = []
    with open(CSV_PATH_BUILDING_ENERGY, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        required_columns = {
            "building_name",
            "room_type",
            "category",
            "category_kwh_per_square_meter",
            "ef_kg_co2eq_per_kwh",
            "energy_type",
            "conversion_factor",
        }
        present_columns = set(reader.fieldnames or [])
        missing_columns = required_columns - present_columns
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(
                "seed_building_energy_factors.csv is missing required columns: "
                f"{missing}"
            )

        for row in reader:
            ef_kg_co2eq_per_kwh = _float_or_none(row.get("ef_kg_co2eq_per_kwh"))
            if ef_kg_co2eq_per_kwh is None:
                continue

            building_name = (row.get("building_name") or "").strip()
            room_type = _normalize_room_type(row.get("room_type"))
            category = (row.get("category") or "").strip().lower()
            energy_type = _normalize_energy_type(row.get("energy_type"))
            if not building_name or not category:
                continue
            emission_type_id = get_factor_emission_type_id(
                data_entry_type=DataEntryTypeEnum.building, factor=row
            )
            classification = {
                "kind": building_name,
                "subkind": category,
                "room_type": room_type,
            }
            if energy_type:
                classification["energy_type"] = energy_type
            factor = await service.prepare_create(
                emission_type_id=emission_type_id,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                classification=classification,
                values={
                    "ef_kg_co2eq_per_kwh": ef_kg_co2eq_per_kwh,
                    "energy_type": energy_type,
                    "conversion_factor": _float_or_none(row.get("conversion_factor")),
                    "category_kwh_per_square_meter": _float_or_none(
                        row.get("category_kwh_per_square_meter")
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
            kgco2 = _float_or_none(row.get("ef_kg_co2eq_per_unit"))
            if kgco2 is None:
                continue
            name = (row.get("name") or "").strip()
            if not name:
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionType.buildings__combustion,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
                classification={
                    "kind": name,
                },
                values={
                    "kg_co2eq_per_unit": kgco2,
                    "unit": (row.get("unit") or "").strip(),
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
