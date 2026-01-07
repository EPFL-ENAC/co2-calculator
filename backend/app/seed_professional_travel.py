"""Seed professional travel data from CSV file."""

import asyncio
import csv
from datetime import datetime
from pathlib import Path

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.inventory import Inventory, InventoryModule
from app.models.location import Location
from app.models.module import Module
from app.models.module_type import ModuleType
from app.models.professional_travel import (
    ProfessionalTravel,
    ProfessionalTravelEmission,
)
from app.services.travel_calculation_service import TravelCalculationService

logger = get_logger(__name__)
settings = get_settings()


async def seed_professional_travel(session: AsyncSession) -> None:
    """Upsert professional travel data from seed_professional_travel.csv."""
    logger.info("Upserting professional travel data...")

    csv_path = Path(__file__).parent.parent / "seed_professional_travel.csv"
    if not csv_path.exists():
        logger.error(f"Professional travel CSV file not found at {csv_path}")
        return

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        upserted = 0
        for row in reader:
            # Parse traveler information
            traveler_id = row.get("traveler_id", "")
            traveler_name = row.get("traveler_name", "")

            # If traveler_id is empty or not provided, use test user IDs
            # This ensures compatibility with test-login principal and standard users
            # Use testuser IDs that match the test login system
            if not traveler_id:
                # Default to standard user ID for test compatibility
                # This matches the test login system: testuser_co2.user.std
                traveler_id = "testuser_co2.user.std"
                if not traveler_name:
                    traveler_name = "Test Standard User"

            # Parse trip details
            origin_name = row.get("origin", "").strip()
            destination_name = row.get("destination", "").strip()

            # Determine transport mode for location lookup
            transport_mode = row.get("transport_mode", "flight")
            # Map "flight" to "plane" for location lookup
            location_transport_mode = "plane" if transport_mode == "flight" else "train"

            # Look up Location IDs from names
            # Try exact match first, then case-insensitive match
            origin_location_stmt = (
                select(Location)
                .where(
                    col(Location.name) == origin_name,
                    col(Location.transport_mode) == location_transport_mode,
                )
                .limit(1)
            )
            origin_result = await session.exec(origin_location_stmt)
            origin_location = origin_result.first()

            # If exact match not found, try case-insensitive
            if not origin_location:
                origin_location_stmt = (
                    select(Location)
                    .where(
                        col(Location.name).ilike(f"%{origin_name}%"),
                        col(Location.transport_mode) == location_transport_mode,
                    )
                    .limit(1)
                )
                origin_result = await session.exec(origin_location_stmt)
                origin_location = origin_result.first()

            destination_location_stmt = (
                select(Location)
                .where(
                    col(Location.name) == destination_name,
                    col(Location.transport_mode) == location_transport_mode,
                )
                .limit(1)
            )
            dest_result = await session.exec(destination_location_stmt)
            destination_location = dest_result.first()

            # If exact match not found, try case-insensitive
            if not destination_location:
                destination_location_stmt = (
                    select(Location)
                    .where(
                        col(Location.name).ilike(f"%{destination_name}%"),
                        col(Location.transport_mode) == location_transport_mode,
                    )
                    .limit(1)
                )
                dest_result = await session.exec(destination_location_stmt)
                destination_location = dest_result.first()

            if not origin_location or not destination_location:
                origin_id = origin_location.id if origin_location else None
                dest_id = destination_location.id if destination_location else None
                logger.warning(
                    f"Skipping row - could not find locations: "
                    f"origin='{origin_name}' (found: {origin_id}), "
                    f"destination='{destination_name}' (found: {dest_id}), "
                    f"transport_mode={location_transport_mode}"
                )
                continue

            # Type narrowing: locations from DB should always have IDs
            if origin_location.id is None or destination_location.id is None:
                logger.warning(
                    f"Skipping row - location missing ID: "
                    f"origin='{origin_name}' (id={origin_location.id}), "
                    f"destination='{destination_name}' (id={destination_location.id})"
                )
                continue

            origin_location_id: int = origin_location.id
            destination_location_id: int = destination_location.id

            departure_date = row.get("departure_date")
            if departure_date:
                departure_date = datetime.strptime(departure_date, "%Y-%m-%d").date()
            else:
                logger.warning(f"Missing departure_date in row: {row}")
                continue

            is_round_trip = row.get("is_round_trip", "false").lower() == "true"

            # Parse transport information (transport_mode already set above)
            class_ = row.get("class_") or None
            distance_km = float(row.get("distance_km", 0.0))
            number_of_trips = int(row.get("number_of_trips", 1))

            # Parse emissions
            kg_co2eq = float(row.get("kg_co2eq", 0.0))

            # Parse organization info
            unit_id = row.get("unit_id", "")
            # Default to test unit IDs if not provided (for test-login compatibility)
            if not unit_id:
                unit_id = "12345"  # ENAC-IT4R test unit
            year = int(row.get("year", departure_date.year))
            provider = row.get("provider", "csv")

            # Check if record already exists (by unique combination)
            # For professional travel, we use traveler_id + departure_date +
            # origin_location_id + destination_location_id as uniqueness
            stmt = select(ProfessionalTravel).where(
                ProfessionalTravel.traveler_id == traveler_id,
                ProfessionalTravel.departure_date == departure_date,
                ProfessionalTravel.origin_location_id == origin_location_id,
                ProfessionalTravel.destination_location_id == destination_location_id,
            )
            result = await session.exec(stmt)
            existing = result.first()

            if existing:
                # Update all fields (excluding emissions - stored separately)
                existing.traveler_name = traveler_name
                existing.is_round_trip = is_round_trip
                existing.transport_mode = transport_mode
                existing.class_ = class_
                existing.number_of_trips = number_of_trips
                existing.unit_id = unit_id
                existing.year = year
                existing.provider = provider
                existing.origin_location_id = origin_location_id
                existing.destination_location_id = destination_location_id

                await session.commit()
                await session.refresh(existing)

                # Update or create emission record
                # Mark existing current emissions as not current
                existing_emission_stmt = select(ProfessionalTravelEmission).where(
                    ProfessionalTravelEmission.professional_travel_id == existing.id,
                    ProfessionalTravelEmission.is_current,
                )
                existing_emission_result = await session.exec(existing_emission_stmt)
                existing_emissions = existing_emission_result.all()
                for emission in existing_emissions:
                    emission.is_current = False

                # Calculate or use provided emissions
                if existing.id:
                    if distance_km > 0 and kg_co2eq > 0:
                        # Use provided values from CSV
                        final_distance_km = distance_km
                        final_kg_co2eq = kg_co2eq
                    else:
                        # Calculate emissions using TravelCalculationService
                        try:
                            calculation_service = TravelCalculationService(session)
                            if transport_mode == "flight":
                                (
                                    final_distance_km,
                                    final_kg_co2eq,
                                ) = await calculation_service.calculate_plane_emissions(
                                    origin_airport=origin_location,
                                    dest_airport=destination_location,
                                    class_=class_,
                                    number_of_trips=number_of_trips,
                                )
                            elif transport_mode == "train":
                                (
                                    final_distance_km,
                                    final_kg_co2eq,
                                ) = await calculation_service.calculate_train_emissions(
                                    origin_station=origin_location,
                                    dest_station=destination_location,
                                    class_=class_,
                                    number_of_trips=number_of_trips,
                                )
                            else:
                                logger.warning(
                                    f"Unknown transport_mode {transport_mode}, "
                                    "skipping emission calculation"
                                )
                                final_distance_km = 0.0
                                final_kg_co2eq = 0.0
                        except Exception as e:
                            logger.warning(
                                f"Failed to calculate emissions for travel "
                                f"{existing.id}: {e}. Using default values."
                            )
                            final_distance_km = distance_km if distance_km > 0 else 0.0
                            final_kg_co2eq = kg_co2eq if kg_co2eq > 0 else 0.0

                    # Create emission record
                    emission = ProfessionalTravelEmission(
                        professional_travel_id=existing.id,
                        distance_km=final_distance_km,
                        kg_co2eq=final_kg_co2eq,
                        formula_version="v1",
                        calculation_inputs={
                            "origin_location_id": origin_location_id,
                            "destination_location_id": destination_location_id,
                            "transport_mode": transport_mode,
                            "class": class_,
                            "number_of_trips": number_of_trips,
                        },
                        is_current=True,
                    )
                    session.add(emission)
                    await session.commit()
            else:
                # Insert new record (without emissions - stored separately)
                travel = ProfessionalTravel(
                    traveler_id=traveler_id,
                    traveler_name=traveler_name,
                    origin_location_id=origin_location_id,
                    destination_location_id=destination_location_id,
                    departure_date=departure_date,
                    is_round_trip=is_round_trip,
                    transport_mode=transport_mode,
                    class_=class_,
                    number_of_trips=number_of_trips,
                    unit_id=unit_id,
                    year=year,
                    provider=provider,
                )
                session.add(travel)
                await session.commit()
                await session.refresh(travel)

                # Calculate or use provided emissions
                if travel.id:
                    if distance_km > 0 and kg_co2eq > 0:
                        # Use provided values from CSV
                        final_distance_km = distance_km
                        final_kg_co2eq = kg_co2eq
                    else:
                        # Calculate emissions using TravelCalculationService
                        try:
                            calculation_service = TravelCalculationService(session)
                            if transport_mode == "flight":
                                (
                                    final_distance_km,
                                    final_kg_co2eq,
                                ) = await calculation_service.calculate_plane_emissions(
                                    origin_airport=origin_location,
                                    dest_airport=destination_location,
                                    class_=class_,
                                    number_of_trips=number_of_trips,
                                )
                            elif transport_mode == "train":
                                (
                                    final_distance_km,
                                    final_kg_co2eq,
                                ) = await calculation_service.calculate_train_emissions(
                                    origin_station=origin_location,
                                    dest_station=destination_location,
                                    class_=class_,
                                    number_of_trips=number_of_trips,
                                )
                            else:
                                logger.warning(
                                    f"Unknown transport_mode {transport_mode}, "
                                    "skipping emission calculation"
                                )
                                final_distance_km = 0.0
                                final_kg_co2eq = 0.0
                        except Exception as e:
                            logger.warning(
                                f"Failed to calculate emissions for travel "
                                f"{travel.id}: {e}. Using default values."
                            )
                            final_distance_km = distance_km if distance_km > 0 else 0.0
                            final_kg_co2eq = kg_co2eq if kg_co2eq > 0 else 0.0

                    # Create emission record
                    emission = ProfessionalTravelEmission(
                        professional_travel_id=travel.id,
                        distance_km=final_distance_km,
                        kg_co2eq=final_kg_co2eq,
                        formula_version="v1",
                        calculation_inputs={
                            "origin_location_id": origin_location_id,
                            "destination_location_id": destination_location_id,
                            "transport_mode": transport_mode,
                            "class": class_,
                            "number_of_trips": number_of_trips,
                        },
                        is_current=True,
                    )
                    session.add(emission)
                    await session.commit()

            upserted += 1

    logger.info(f"Upserted {upserted} professional travel records from CSV")


async def sync_to_modules_table(session: AsyncSession) -> None:
    """Sync professional_travels data to the generic modules table."""
    from collections import defaultdict
    from typing import Optional

    from sqlalchemy import Text, cast

    logger.info("Syncing professional travel data to modules table...")

    # Get the module_type for professional-travel
    module_type_stmt = select(ModuleType).where(
        ModuleType.name == "professional-travel"
    )
    module_type_result = await session.exec(module_type_stmt)
    module_type: Optional[ModuleType] = module_type_result.first()

    if not module_type:
        logger.error("Module type 'professional-travel' not found in database")
        return

    logger.info(f"Found module_type: id={module_type.id}, name={module_type.name}")

    # Get all professional travel records
    travel_stmt = select(ProfessionalTravel)
    travel_result = await session.exec(travel_stmt)
    travels = list(travel_result.all())

    logger.info(f"Found {len(travels)} professional travel records to sync")

    # Group travels by (unit_id, year) to find/create inventory_modules
    travels_by_inventory = defaultdict(list)

    for travel_record in travels:
        key = (travel_record.unit_id, travel_record.year)
        travels_by_inventory[key].append(travel_record)

    total_synced = 0

    for (unit_id, year), travel_list in travels_by_inventory.items():
        # Find or create Inventory
        inventory_stmt = select(Inventory).where(
            Inventory.unit_id == unit_id, Inventory.year == year
        )
        inventory_result = await session.exec(inventory_stmt)
        inventory: Optional[Inventory] = inventory_result.first()

        if not inventory:
            logger.info(f"Creating inventory for unit_id={unit_id}, year={year}")
            inventory = Inventory(unit_id=unit_id, year=year)
            session.add(inventory)
            await session.flush()  # Get the ID

        # Find or create InventoryModule
        inventory_module_stmt = select(InventoryModule).where(
            InventoryModule.inventory_id == inventory.id,
            InventoryModule.module_type_id == module_type.id,
        )
        inventory_module_result = await session.exec(inventory_module_stmt)
        inventory_module: Optional[InventoryModule] = inventory_module_result.first()

        if not inventory_module:
            logger.info(
                f"Creating inventory_module for inventory_id={inventory.id}, "
                f"module_type_id={module_type.id}"
            )
            inventory_module = InventoryModule(
                inventory_id=inventory.id,
                module_type_id=module_type.id,
                status=1,  # in_progress
            )
            session.add(inventory_module)
            await session.flush()  # Get the ID

        # Now create Module entries for each travel
        for travel_record in travel_list:
            # Check if module entry already exists for this travel
            # Use cast to text for JSON field comparison
            if travel_record.id is None:
                logger.warning(
                    f"Skipping travel record without ID: "
                    f"traveler={travel_record.traveler_name}"
                )
                continue

            module_stmt = select(Module).where(
                Module.module_type_id == module_type.id,
                Module.inventory_module_id == inventory_module.id,
                cast(Module.data["id"], Text) == str(travel_record.id),
            )
            module_result = await session.exec(module_stmt)
            existing_module: Optional[Module] = module_result.first()

            if not existing_module:
                # Create the module entry with travel data as JSON
                module_data = {
                    "id": travel_record.id,
                    "traveler_id": travel_record.traveler_id,
                    "traveler_name": travel_record.traveler_name,
                    "origin_location_id": travel_record.origin_location_id,
                    "destination_location_id": travel_record.destination_location_id,
                    "departure_date": travel_record.departure_date.isoformat()
                    if travel_record.departure_date
                    else None,
                    "is_round_trip": travel_record.is_round_trip,
                    "transport_mode": travel_record.transport_mode,
                    "class": travel_record.class_,
                    "number_of_trips": travel_record.number_of_trips,
                    "unit_id": travel_record.unit_id,
                    "year": travel_record.year,
                    "provider": travel_record.provider,
                }

                module = Module(
                    module_type_id=module_type.id,
                    variant_type_id=None,  # Professional travel has no variants
                    inventory_module_id=inventory_module.id,
                    data=module_data,
                )
                session.add(module)
                total_synced += 1

    await session.commit()
    logger.info(f"Synced {total_synced} professional travel records to modules table")


async def main() -> None:
    """Main seed function."""
    logger.info("Starting professional travel seeding...")

    async with SessionLocal() as session:
        await seed_professional_travel(session)
        await sync_to_modules_table(session)

    logger.info("Professional travel seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
