"""Seed Archibus room data from CSV for the Buildings module."""

import asyncio
import csv
from pathlib import Path
from typing import Optional

from sqlmodel import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.archibus_room import ArchibusRoom

logger = get_logger(__name__)

CSV_PATH = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_buildings_archibus_rooms.csv"
)


def _to_float(value: Optional[str]) -> Optional[float]:
    """Best-effort float conversion for CSV values."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized == "-":
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


async def seed_archibus_rooms(session: AsyncSession) -> None:
    """Seed (or re-seed) Archibus rooms from CSV."""
    await session.exec(delete(ArchibusRoom))

    rooms: list[ArchibusRoom] = []
    with open(CSV_PATH, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            room = ArchibusRoom(
                unit_institutional_id=(row.get("unit_institutional_id") or "").strip()
                or None,
                building_location=row["building_location"].strip(),
                building_name=row["building_name"].strip(),
                room_name=row["room_name"].strip(),
                room_type=(row.get("room_type") or "").strip() or None,
                room_surface_square_meter=_to_float(
                    row.get("room_surface_square_meter")
                ),
                heating_kwh_per_square_meter=_to_float(
                    row.get("heating_kwh_per_square_meter")
                ),
                cooling_kwh_per_square_meter=_to_float(
                    row.get("cooling_kwh_per_square_meter")
                ),
                ventilation_kwh_per_square_meter=_to_float(
                    row.get("ventilation_kwh_per_square_meter")
                ),
                lighting_kwh_per_square_meter=_to_float(
                    row.get("lighting_kwh_per_square_meter")
                ),
                note=(row.get("note") or row.get("notes") or "").strip() or None,
                kg_co2eq=_to_float(row.get("emissions") or row.get("kg_co2eq")),
            )
            rooms.append(room)

    session.add_all(rooms)
    await session.commit()
    logger.info(f"Seeded {len(rooms)} Archibus rooms.")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_archibus_rooms(session)


if __name__ == "__main__":
    asyncio.run(main())
