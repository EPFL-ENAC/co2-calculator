"""Seed professional travel data from seed_travel_flight.csv.

This script populates the professional_travels table with travel data:
- Loads travel records from seed_travel_flight.csv
- Maps CSV columns to ProfessionalTravel model fields
- Looks up locations by IATA code or name
- Looks up units by cost center
- Handles round trips
- Sets provider, year, and other fields
"""

import asyncio
import csv
from datetime import date as dt_date
from pathlib import Path
from typing import Dict, Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import IngestionMethod
from app.models.location import Location
from app.models.professional_travel import ProfessionalTravel
from app.models.unit import Unit
from app.models.user import User, UserProvider
from app.services.unit_service import UnitService

logger = get_logger(__name__)
settings = get_settings()

CSV_PATH = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "seed_professional_travel_data.csv"
)


def parse_date(date_str: str) -> Optional[dt_date]:
    """Parse date from CSV format (YYYYMMDD, e.g., '20250525')."""
    if not date_str or not date_str.strip():
        return None
    try:
        # Format is YYYYMMDD
        if len(date_str) == 8:
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            return dt_date(year, month, day)
    except (ValueError, IndexError) as e:
        logger.warning(f"Could not parse date: {date_str}, error: {e}")
    return None


async def seed_professional_travel(session: AsyncSession) -> None:
    """Upsert professional travel data from seed_professional_travel_data.csv.

    CSV columns should match ProfessionalTravel table fields:
    - traveler_id (optional)
    - traveler_name
    - origin_location_name, origin_location_iata (for lookup)
    - destination_location_name, destination_location_iata (for lookup)
    - departure_date
    - is_round_trip
    - transport_mode (flight or train)
    - class (class_1, class_2, eco, eco_plus, business, first)
    - number_of_trips
    - unit_provider_code (for lookup)
    - provider (ACCRED, DEFAULT, TEST)
    - provider_source (api, csv, manual)
    - year
    """
    logger.info("Upserting professional travel data...")

    csv_path = CSV_PATH
    if not csv_path.exists():
        logger.error(f"Professional travel CSV file not found at {csv_path}")
        return

    # Ensure the 'unknown' principal user exists
    user_stmt = select(User).where(User.provider_code == "unknown")
    user_result = await session.exec(user_stmt)
    unknown_user = user_result.one_or_none()
    if unknown_user is None:
        unknown_user = User(
            provider_code="unknown",
            email="unknown@placeholder",
            provider=UserProvider.ACCRED,
            display_name="Unknown Principal User",
        )
        session.add(unknown_user)
        await session.commit()
        logger.info("Created placeholder 'unknown' principal user.")

    unit_service = UnitService(session)

    # Build location lookup cache by IATA code and name
    logger.info("Building location lookup cache...")
    location_result = await session.exec(select(Location))
    locations_by_iata: Dict[str, Location] = {}
    # Key by (name.upper().strip(), transport_mode) to handle same name different modes
    # Also create a fallback dict keyed by name only (without transport_mode)
    # for fuzzy matching
    locations_by_name: Dict[Tuple[str, str], Location] = {}
    locations_by_name_only: Dict[str, Location] = {}  # For fallback lookup
    for loc in location_result.all():
        if loc.iata_code:
            locations_by_iata[loc.iata_code.upper().strip()] = loc
        name_key = loc.name.upper().strip()
        locations_by_name[(name_key, loc.transport_mode)] = loc
        # Store first occurrence for name-only lookup (prefer matching transport_mode)
        if name_key not in locations_by_name_only:
            locations_by_name_only[name_key] = loc
    logger.info(
        f"Loaded {len(locations_by_iata)} locations with IATA codes, "
        f"{len(locations_by_name)} total locations"
    )

    upserted = 0
    skipped = 0
    errors = 0

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Parse fields from CSV - using table column names
                traveler_id_str = row.get("traveler_id", "").strip()
                traveler_id = int(traveler_id_str) if traveler_id_str else None

                traveler_name = row.get("traveler_name", "").strip()
                if not traveler_name:
                    logger.warning(f"Row {row_num}: Missing traveler_name, skipping")
                    skipped += 1
                    continue

                # Parse departure date
                departure_date_str = row.get("departure_date", "").strip()
                departure_date = None
                if departure_date_str:
                    # Try parsing as YYYY-MM-DD or YYYYMMDD
                    if len(departure_date_str) == 8 and departure_date_str.isdigit():
                        departure_date = parse_date(departure_date_str)
                    else:
                        try:
                            departure_date = dt_date.fromisoformat(departure_date_str)
                        except ValueError:
                            departure_date = parse_date(departure_date_str)

                if not departure_date:
                    logger.warning(
                        f"Row {row_num}: Could not parse departure_date "
                        f"'{departure_date_str}', skipping"
                    )
                    skipped += 1
                    continue

                # Parse year (use from CSV or calculate from date)
                year_str = row.get("year", "").strip()
                if year_str:
                    try:
                        year = int(year_str)
                    except ValueError:
                        year = departure_date.year
                else:
                    year = departure_date.year

                # Parse transport mode
                transport_mode = row.get("transport_mode", "").strip().lower()
                if transport_mode not in ("flight", "train"):
                    logger.warning(
                        f"Row {row_num}: Invalid transport_mode "
                        f"'{transport_mode}', skipping"
                    )
                    skipped += 1
                    continue

                # Parse class (already in correct format:
                # class_1, class_2, eco, eco_plus, business, first)
                class_ = row.get("class", "").strip() or None

                # Parse is_round_trip
                is_round_trip_str = row.get("is_round_trip", "").strip().lower()
                is_round_trip = is_round_trip_str in ("true", "1", "yes")

                # Parse number of trips
                try:
                    number_of_trips = int(
                        row.get("number_of_trips", "1").strip() or "1"
                    )
                except ValueError:
                    number_of_trips = 1

                # Lookup origin location
                origin_iata = row.get("origin_location_iata", "").strip()
                origin_name = row.get("origin_location_name", "").strip()
                origin_location = None

                if origin_iata:
                    origin_location = locations_by_iata.get(origin_iata.upper().strip())
                if not origin_location and origin_name:
                    # Normalize name for lookup (uppercase and strip)
                    origin_name_normalized = origin_name.upper().strip()
                    # Try lookup by name with transport mode first
                    origin_location = locations_by_name.get(
                        (origin_name_normalized, transport_mode)
                    )
                    # Fallback: try without transport mode filter
                    if not origin_location:
                        origin_location = locations_by_name_only.get(
                            origin_name_normalized
                        )

                if not origin_location:
                    logger.warning(
                        f"Row {row_num}: Could not find origin location "
                        f"(IATA: {origin_iata}, Name: {origin_name}, "
                        f"Transport: {transport_mode}), skipping"
                    )
                    skipped += 1
                    continue

                # Verify we have location ID
                if not origin_location.id:
                    logger.error(
                        f"Row {row_num}: Origin location found but has no ID: "
                        f"{origin_location.name}, skipping"
                    )
                    skipped += 1
                    continue

                # Lookup destination location
                dest_iata = row.get("destination_location_iata", "").strip()
                dest_name = row.get("destination_location_name", "").strip()
                dest_location = None

                if dest_iata:
                    dest_location = locations_by_iata.get(dest_iata.upper().strip())
                if not dest_location and dest_name:
                    # Normalize name for lookup (uppercase and strip)
                    dest_name_normalized = dest_name.upper().strip()
                    # Try lookup by name with transport mode first
                    dest_location = locations_by_name.get(
                        (dest_name_normalized, transport_mode)
                    )
                    # Fallback: try without transport mode filter
                    if not dest_location:
                        dest_location = locations_by_name_only.get(dest_name_normalized)

                if not dest_location:
                    logger.warning(
                        f"Row {row_num}: Could not find destination location "
                        f"(IATA: {dest_iata}, Name: {dest_name}, "
                        f"Transport: {transport_mode}), skipping"
                    )
                    skipped += 1
                    continue

                # Verify we have location ID
                if not dest_location.id:
                    logger.error(
                        f"Row {row_num}: Destination location found but has no ID: "
                        f"{dest_location.name}, skipping"
                    )
                    skipped += 1
                    continue

                # Get or create unit by provider_code
                unit_provider_code = row.get("unit_provider_code", "").strip()
                if not unit_provider_code:
                    logger.warning(
                        f"Row {row_num}: Missing unit_provider_code, skipping"
                    )
                    skipped += 1
                    continue

                unit_stmt = select(Unit).where(
                    Unit.provider_code == unit_provider_code,
                    Unit.provider == UserProvider.ACCRED,
                )
                unit_result = await session.exec(unit_stmt)
                unit = unit_result.one_or_none()
                unit_id = unit.id if unit else None

                if not unit_id:
                    # Create unit with default values
                    new_unit = await unit_service.upsert(
                        unit_data=Unit(
                            provider_code=unit_provider_code,
                            provider=UserProvider.ACCRED,
                            name=f"Unit {unit_provider_code}",
                            principal_user_provider_code=unknown_user.provider_code,
                            cost_centers=[unit_provider_code],
                            affiliations=[],
                        ),
                    )
                    if new_unit is None or new_unit.id is None:
                        logger.warning(
                            f"Row {row_num}: Failed to create unit for "
                            f"provider_code {unit_provider_code}, skipping"
                        )
                        skipped += 1
                        continue
                    unit_id = new_unit.id

                # Parse provider and provider_source
                provider_str = row.get("provider", "ACCRED").strip().upper()
                try:
                    provider = UserProvider[provider_str]
                except KeyError:
                    provider = UserProvider.ACCRED

                provider_source_str = row.get("provider_source", "csv").strip().lower()
                try:
                    provider_source = IngestionMethod[provider_source_str]
                except KeyError:
                    provider_source = IngestionMethod.csv

                # Check if travel record already exists
                # Use a combination of fields to identify duplicates
                travel_stmt = select(ProfessionalTravel).where(
                    ProfessionalTravel.unit_id == unit_id,
                    ProfessionalTravel.year == year,
                    ProfessionalTravel.origin_location_id == origin_location.id,
                    ProfessionalTravel.destination_location_id == dest_location.id,
                    ProfessionalTravel.departure_date == departure_date,
                    ProfessionalTravel.traveler_name == traveler_name,
                    ProfessionalTravel.transport_mode == transport_mode,
                )
                travel_result = await session.exec(travel_stmt)
                existing = travel_result.first()

                if existing:
                    # Update existing record
                    existing.traveler_id = traveler_id
                    existing.traveler_name = traveler_name
                    existing.class_ = class_
                    existing.is_round_trip = is_round_trip
                    existing.number_of_trips = number_of_trips
                    existing.provider = provider
                    existing.provider_source = provider_source
                else:
                    # Create new record using location IDs (not names)
                    # - all fields match table columns
                    travel = ProfessionalTravel(
                        traveler_id=traveler_id,  # Optional, can be linked later
                        traveler_name=traveler_name,
                        origin_location_id=origin_location.id,  # Using location ID
                        destination_location_id=dest_location.id,  # Using location ID
                        departure_date=departure_date,
                        is_round_trip=is_round_trip,
                        transport_mode=transport_mode,
                        class_=class_,
                        number_of_trips=number_of_trips,
                        unit_id=unit_id,
                        provider=provider,
                        provider_source=provider_source,
                        year=year,
                    )
                    session.add(travel)
                    logger.debug(
                        f"Row {row_num}: Creating travel record with "
                        f"origin_location_id={origin_location.id} "
                        f"({origin_location.name}), "
                        f"destination_location_id={dest_location.id} "
                        f"({dest_location.name}), unit_id={unit_id}"
                    )

                upserted += 1

                # Commit in batches for performance
                if upserted % 100 == 0:
                    await session.commit()
                    logger.info(f"Processed {upserted} travel records...")

            except Exception as e:
                logger.error(f"Row {row_num}: Error processing row: {e}")
                logger.debug(f"Row data: {row}")
                errors += 1
                continue

    await session.commit()
    logger.info(
        f"Professional travel seeding complete! "
        f"Upserted {upserted} records, skipped {skipped} rows, "
        f"{errors} errors"
    )


async def main() -> None:
    """Main seed function."""
    logger.info("Starting professional travel seeding...")

    async with SessionLocal() as session:
        await seed_professional_travel(session)

    logger.info("Professional travel seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
