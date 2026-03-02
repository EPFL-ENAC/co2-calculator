"""Seed locations (train stations and airports) from split CSV data."""

import asyncio
import csv
from pathlib import Path
from typing import TypeAlias

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.location import PlaneLocation, TrainLocation
from app.modules.professional_travel import (
    schemas as schemas,
)  # This ensures the handlers are registered

logger = get_logger(__name__)


SEED_DIR = Path(__file__).parent.parent.parent / "seed_data"
CSV_PATH_PLANE = SEED_DIR / "seed_travel_location_plane.csv"
CSV_PATH_TRAIN = SEED_DIR / "seed_travel_location_train.csv"


async def seed_locations(session: AsyncSession) -> None:
    """Seed locations from split plane/train CSV files."""
    logger.info("Seeding locations from split CSV files...")

    LocationModel: TypeAlias = type[PlaneLocation] | type[TrainLocation]
    LocationRow: TypeAlias = PlaneLocation | TrainLocation

    csv_sources: list[tuple[Path, LocationModel]] = [
        (CSV_PATH_PLANE, PlaneLocation),
        (CSV_PATH_TRAIN, TrainLocation),
    ]
    missing_files = [str(path) for path, _cls in csv_sources if not path.exists()]
    if missing_files:
        logger.error(f"Missing required CSV files: {', '.join(missing_files)}")
        return

    # Load existing locations into a dict keyed by (name, table class)
    existing_locations: dict[tuple[str, LocationModel], LocationRow] = {}
    plane_result = await session.exec(select(PlaneLocation))
    existing_locations.update(
        {(loc.name.lower(), PlaneLocation): loc for loc in plane_result.all()}
    )
    train_result = await session.exec(select(TrainLocation))
    existing_locations.update(
        {(loc.name.lower(), TrainLocation): loc for loc in train_result.all()}
    )
    existing_count = len(existing_locations)
    logger.info(f"Found {existing_count} existing locations in database")

    # Read and parse CSV files
    locations_to_insert: list[LocationRow] = []
    locations_to_update: list[LocationRow] = []
    skipped = 0
    updated_count = 0

    for csv_path, location_cls in csv_sources:
        logger.info(f"Processing location seed file: {csv_path.name}")
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(
                reader, start=2
            ):  # Start at 2 (row 1 is header)
                try:
                    # Parse name
                    name = row.get("name", "").strip()
                    if not name:
                        logger.warning(
                            f"{csv_path.name} row {row_num}: Missing name, skipping"
                        )
                        skipped += 1
                        continue

                    # Parse airport_size (optional, only for planes)
                    airport_size_raw = row.get("airport_size", "").strip()
                    airport_size = None
                    if airport_size_raw:
                        airport_size_lower = airport_size_raw.lower()
                        if airport_size_lower not in (
                            "medium_airport",
                            "large_airport",
                        ):
                            logger.warning(
                                f"{csv_path.name} row {row_num}: Invalid airport_size "
                                f"'{airport_size_raw}', skipping"
                            )
                            skipped += 1
                            continue
                        airport_size = airport_size_lower

                    # Parse coordinates
                    try:
                        latitude = float(row.get("latitude", "").strip())
                        longitude = float(row.get("longitude", "").strip())
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"{csv_path.name} row {row_num}: Invalid coordinates "
                            f"(lat: {row.get('latitude')}, "
                            f"lon: {row.get('longitude')}), skipping: {e}"
                        )
                        skipped += 1
                        continue

                    # Parse optional fields (convert empty strings to None)
                    continent = row.get("continent", "").strip() or None
                    country_code = row.get("country_code", "").strip() or None
                    municipality = row.get("municipality", "").strip() or None
                    iata_code = row.get("iata_code", "").strip() or None
                    keywords = row.get("keywords", "").strip() or None

                    # Check if location already exists
                    location_key = (name.lower(), location_cls)
                    existing_location = existing_locations.get(location_key)

                    if existing_location:
                        # Update existing location with new data
                        needs_update = False
                        if existing_location.airport_size != airport_size:
                            existing_location.airport_size = airport_size
                            needs_update = True
                        if existing_location.continent != continent:
                            existing_location.continent = continent
                            needs_update = True
                        if existing_location.country_code != country_code:
                            existing_location.country_code = country_code
                            needs_update = True
                        if existing_location.municipality != municipality:
                            existing_location.municipality = municipality
                            needs_update = True
                        if existing_location.iata_code != iata_code:
                            existing_location.iata_code = iata_code
                            needs_update = True
                        if existing_location.keywords != keywords:
                            existing_location.keywords = keywords
                            needs_update = True

                        if needs_update:
                            locations_to_update.append(existing_location)
                            updated_count += 1
                    else:
                        # Create new location
                        location = location_cls(
                            name=name,
                            airport_size=airport_size,
                            latitude=latitude,
                            longitude=longitude,
                            continent=continent,
                            country_code=country_code,
                            municipality=municipality,
                            iata_code=iata_code,
                            keywords=keywords,
                        )
                        locations_to_insert.append(location)

                except Exception as e:
                    logger.error(
                        f"{csv_path.name} row {row_num}: Error processing row: {e}"
                    )
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
        f"updated {updated_count} existing locations, "
        f"skipped {skipped} rows"
    )


async def main() -> None:
    """Main seed function."""
    logger.info("Starting locations seeding...")

    async with SessionLocal() as session:
        await seed_locations(session)

    logger.info("Locations seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
