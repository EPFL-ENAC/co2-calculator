"""Seed building room data from CSV for the Buildings module."""

import asyncio
import csv
from pathlib import Path
from typing import Optional

from sqlmodel import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.building_room import BuildingRoom

logger = get_logger(__name__)

CSV_PATH = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_building_rooms_reference.csv"
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


async def seed_building_rooms(session: AsyncSession) -> None:
    """Seed (or re-seed) building rooms from CSV."""
    await session.exec(delete(BuildingRoom))

    rooms: list[BuildingRoom] = []
    with open(CSV_PATH, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            room = BuildingRoom(
                building_location=row["building_location"].strip(),
                building_name=row["building_name"].strip(),
                room_name=row["room_name"].strip(),
                room_type=(row.get("room_type") or "").strip() or None,
                room_surface_square_meter=_to_float(
                    row.get("room_surface_square_meter")
                ),
            )
            rooms.append(room)

    session.add_all(rooms)
    await session.commit()
    logger.info(f"Seeded {len(rooms)} building rooms.")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_building_rooms(session)


if __name__ == "__main__":
    asyncio.run(main())
