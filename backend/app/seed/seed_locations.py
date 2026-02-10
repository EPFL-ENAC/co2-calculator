"""Seed locations (train stations and airports) from CSV data.

This script populates the locations table with train stations and airports
from travel_destination.csv file.
"""

import asyncio
import csv
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.location import Location

logger = get_logger(__name__)


CSV_PATH = (
    Path(__file__).parent.parent.parent / "seed_data" / "seed_travel_destination.csv"
)


async def seed_locations(session: AsyncSession) -> None:
    """Seed locations from travel_destination.csv."""
    logger.info("Seeding locations from CSV...")

    # Find the CSV file
    csv_path = CSV_PATH
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    # Load existing locations into a dict keyed by (name, transport_mode)
    result = await session.exec(select(Location))
    existing_locations = {
        (loc.name.lower(), loc.transport_mode): loc for loc in result.all()
    }
    existing_count = len(existing_locations)
    logger.info(f"Found {existing_count} existing locations in database")

    # Read and parse CSV
    locations_to_insert = []
    locations_to_update = []
    skipped = 0
    updated_count = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Parse transport mode
                transport_mode_raw = row.get("type", "").strip().lower()
                if transport_mode_raw == "train":
                    transport_mode = "train"
                elif transport_mode_raw == "plane":
                    transport_mode = "plane"
                else:
                    logger.warning(
                        f"Row {row_num}: Invalid transport mode "
                        f"'{transport_mode_raw}', skipping"
                    )
                    skipped += 1
                    continue

                # Parse name
                name = row.get("name", "").strip()
                if not name:
                    logger.warning(f"Row {row_num}: Missing name, skipping")
                    skipped += 1
                    continue

                # Parse coordinates
                try:
                    latitude = float(row.get("latitude", "").strip())
                    longitude = float(row.get("longitude", "").strip())
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Row {row_num}: Invalid coordinates "
                        f"(lat: {row.get('latitude')}, "
                        f"lon: {row.get('longitude')}), skipping: {e}"
                    )
                    skipped += 1
                    continue

                # Parse IATA code (optional, only for planes)
                iata_code = row.get("iata_code", "").strip()
                if not iata_code:
                    iata_code = None

                # Parse country code (optional)
                countrycode = row.get("country code", "").strip()
                if not countrycode:
                    countrycode = None

                # Check if location already exists
                location_key = (name.lower(), transport_mode)
                existing_location = existing_locations.get(location_key)

                if existing_location:
                    # Update existing location with countrycode if missing or different
                    if existing_location.countrycode != countrycode:
                        existing_location.countrycode = countrycode
                        locations_to_update.append(existing_location)
                        updated_count += 1
                else:
                    # Create new location
                    location = Location(
                        transport_mode=transport_mode,
                        name=name,
                        latitude=latitude,
                        longitude=longitude,
                        iata_code=iata_code,
                        countrycode=countrycode,
                    )
                    locations_to_insert.append(location)

            except Exception as e:
                logger.error(f"Row {row_num}: Error processing row: {e}")
                logger.debug(f"Row data: {row}")
                skipped += 1
                continue

    # Update existing locations in batches
    if locations_to_update:
        batch_size = 1000
        for i in range(0, len(locations_to_update), batch_size):
            batch = locations_to_update[i : i + batch_size]
            for loc in batch:
                session.add(loc)
            await session.commit()
            logger.info(
                f"Updated batch: {min(i + batch_size, len(locations_to_update))}/"
                f"{len(locations_to_update)} locations"
            )

    # Bulk insert new locations in batches
    total_inserted = 0
    if locations_to_insert:
        batch_size = 1000
        for i in range(0, len(locations_to_insert), batch_size):
            batch = locations_to_insert[i : i + batch_size]
            session.add_all(batch)
            await session.commit()
            total_inserted += len(batch)
            logger.info(
                f"Inserted batch: {total_inserted}/{len(locations_to_insert)} locations"
            )

    logger.info(
        f"Location seeding complete! "
        f"Inserted {total_inserted} new locations, "
        f"updated {updated_count} existing locations with countrycode, "
        f"skipped {skipped} rows"
    )


async def main() -> None:
    """Main seed function."""
    logger.info("Starting locations seeding...")

    async with SessionLocal() as session:
        await seed_locations(session)

    logger.info("Locations seeding complete!")


if __name__ == "__main__":
    # Run script on /app/api/v1/travel_destination.csv
    asyncio.run(main())
