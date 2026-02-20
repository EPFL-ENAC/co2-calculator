"""Seed Archibus room data from CSV for the Buildings module."""

import asyncio
import csv
from pathlib import Path

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.archibus_room import ArchibusRoom

logger = get_logger(__name__)

CSV_PATH = Path(__file__).parent.parent.parent / "seed_data" / "seed_archibus_rooms.csv"


async def seed_archibus_rooms(session: AsyncSession) -> None:
    """Seed (or re-seed) Archibus rooms from CSV."""
    await session.execute(text("DELETE FROM archibus_rooms"))

    rooms: list[ArchibusRoom] = []
    with open(CSV_PATH, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            room = ArchibusRoom(
                building_name=row["building_name"],
                building_code=row["building_code"],
                room_code=row["room_code"],
                room_name=row["room_name"],
                generic_type_din=row["generic_type_din"],
                sia_type=row["sia_type"],
                surface_m2=float(row["surface_m2"]),
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
