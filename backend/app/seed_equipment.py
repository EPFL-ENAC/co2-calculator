"""Seed equipment inventory from synth_data.csv with power factor lookups.

This script populates the equipment table with real equipment data:
- Loads equipment from synth_data.csv
- Enriches with power factors from table_power.csv lookup
- Creates equipment records with realistic usage patterns
- Links to power_factor_id when match found
- Calculates and seeds equipment_emissions for all equipment
"""

import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.emission_factor import EmissionFactor, PowerFactor
from app.models.equipment import Equipment, EquipmentEmission
from app.services import calculation_service

logger = get_logger(__name__)
settings = get_settings()


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from CSV format (e.g., '12/7/2024')."""
    if not date_str:
        return None
    try:
        # Assuming format is MM/DD/YYYY
        parts = date_str.split("/")
        if len(parts) == 3:
            month, day, year = parts
            return datetime(int(year), int(month), int(day))
    except (ValueError, IndexError):
        logger.warning(f"Could not parse date: {date_str}")
    return None


async def load_power_factors_map(session: AsyncSession) -> Dict[str, PowerFactor]:
    """Load power factors from database into a lookup dictionary."""
    logger.info("Loading power factors from database...")

    result = await session.exec(select(PowerFactor))
    power_factors_list = result.all()

    # Create lookup dictionary with multiple key strategies
    power_factors_map = {}

    for pf in power_factors_list:
        # Strategy 1: Full match with sub_class
        if pf.sub_class:
            key_full = (
                f"{pf.submodule.lower()}:"
                f"{pf.equipment_class.lower()}:{pf.sub_class.lower()}"
            )
            power_factors_map[key_full] = pf

        # Strategy 2: Match without sub_class (fallback)
        key_class = f"{pf.submodule.lower()}:{pf.equipment_class.lower()}"
        if key_class not in power_factors_map:
            power_factors_map[key_class] = pf

    logger.info(
        f"Loaded {len(power_factors_list)} power"
        f" factors with {len(power_factors_map)} lookup keys"
    )
    return power_factors_map


def normalize_equipment_class(equipment_class: str) -> str:
    """Normalize equipment class for case-insensitive matching."""
    # Class names are mostly unique in table_power.csv
    # Just normalize to lowercase for matching
    return equipment_class.lower().strip()


def lookup_power_factor(
    equipment_class: str,
    power_factors_map: Dict[str, PowerFactor],
) -> Optional[PowerFactor]:
    """
    Lookup power factor for equipment by class name only.

    Searches across all submodules since class names are mostly unique.
    Returns None if no match found OR if multiple matches exist (ambiguous).

    Logic:
    - If 0 matches: Returns None (no power factor available)
    - If 1 match: Returns the power factor (unambiguous)
    - If >1 matches: Returns first match for testing, logs warning (sub-class required)
    """
    normalized_class = normalize_equipment_class(equipment_class)

    # Find ALL matching power factors across all submodules
    matches = [
        pf
        for pf in power_factors_map.values()
        if pf.equipment_class.lower() == normalized_class
    ]

    if len(matches) == 0:
        # No power factor found
        return None
    elif len(matches) == 1:
        # Unambiguous match
        return matches[0]
    else:
        # Multiple matches - ambiguous, requires sub-class
        # For testing purposes, return first match but log warning
        sub_classes = [pf.sub_class for pf in matches if pf.sub_class]
        logger.warning(
            f"Class '{equipment_class}' has {len(matches)} power factors "
            f"with different sub-classes: {sub_classes}. "
            f"Sub-class selection required. Using first match for testing."
        )
        return matches[0]  # Temporary: return first match for testing


async def seed_equipment(session: AsyncSession) -> None:
    """Seed equipment from synth_data.csv."""
    logger.info("Seeding equipment from CSV...")

    # Delete existing equipment emissions first (to avoid FK constraint violation)
    result = await session.exec(select(EquipmentEmission))
    existing_emissions = result.all()

    if existing_emissions:
        logger.info(f"Deleting {len(existing_emissions)} existing emission records...")
        for emission in existing_emissions:
            await session.delete(emission)
        await session.commit()

    # Now delete existing equipment
    eq_result = await session.exec(select(Equipment))
    existing_equipment: List[Equipment] = list(eq_result.all())

    if existing_equipment:
        logger.info(f"Deleting {len(existing_equipment)} existing equipment records...")
        for equipment in existing_equipment:
            await session.delete(equipment)
        await session.commit()

    # Load power factors for lookup
    power_factors_map = await load_power_factors_map(session)

    # Find the CSV file
    csv_path = Path(__file__).parent / "api" / "v1" / "synth_data.csv"
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    # Read and parse CSV
    equipment_list: List[Equipment] = []
    matched_count = 0
    no_match_count = 0
    ambiguous_classes: Dict[str, int] = {}  # Track classes requiring sub-class

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            cost_center = row.get("Cost Center", "").strip()
            cost_center_desc = row.get("Cost Center FR Description", "").strip()
            name = row.get("Name 1", "").strip()
            category = row.get("Category", "").strip()
            equipment_class = row.get("Class", "").strip()
            # Find all matching power factors for this class
            all_matches = [
                pf
                for pf in power_factors_map.values()
                if pf.equipment_class.lower() == equipment_class.lower()
            ]

            # If class has multiple power factors,
            # assign first one's sub-class for testing
            if len(all_matches) > 1:
                equipment_subclass = all_matches[0].sub_class
            else:
                equipment_subclass = None
            service_date_str = row.get("Service Date", "").strip()
            status = row.get("Status", "In service").strip()

            if not name or not category or not equipment_class:
                logger.warning(f"Skipping row {idx} with missing data: {row}")
                continue

            # Lookup power factor - returns None if not found or ambiguous
            power_factor = lookup_power_factor(equipment_class, power_factors_map)

            if power_factor is None:
                # No power factor found
                logger.warning(
                    f"Row {idx} - {name}: No power factor found for class "
                    f"'{equipment_class}'. Equipment will be created without "
                    f"power factor (no emissions calculated)."
                )
                no_match_count += 1
                power_factor_id = None
                submodule = category  # Fallback to original category
            else:
                matched_count += 1
                power_factor_id = power_factor.id
                # Derive submodule from the matched power factor
                submodule = power_factor.submodule

                # Check if this class has multiple power factors (ambiguous)
                all_matches = [
                    pf
                    for pf in power_factors_map.values()
                    if pf.equipment_class.lower() == equipment_class.lower()
                ]
                if len(all_matches) > 1:
                    ambiguous_classes[equipment_class] = (
                        ambiguous_classes.get(equipment_class, 0) + 1
                    )

            # Use power_factor_id - actual values will be looked up at calculation time
            active_power_w = None
            standby_power_w = None

            # Generate realistic usage patterns based on equipment type
            # Use hash for deterministic but varied values
            name_hash = abs(hash(name)) % 100

            if (
                "server" in equipment_class.lower()
                or "freezer" in equipment_class.lower()
            ):
                active_usage_pct = 70.0 + (name_hash % 20)  # 70-90%
            elif submodule == "scientific":
                active_usage_pct = 10.0 + (name_hash % 20)  # 10-30%
            else:
                active_usage_pct = 20.0 + (name_hash % 20)  # 20-40%

            passive_usage_pct = 100.0 - active_usage_pct

            # Parse service date
            service_date = parse_date(service_date_str)

            equipment_local = Equipment(
                cost_center=cost_center,
                cost_center_description=cost_center_desc or None,
                name=name,
                category=category,  # Original category from synth_data
                submodule=submodule,  # Mapped submodule for grouping
                equipment_class=equipment_class,
                sub_class=equipment_subclass,  # Not in synth_data.csv
                service_date=service_date,
                status=status,
                active_usage_pct=active_usage_pct,
                passive_usage_pct=passive_usage_pct,
                active_power_w=active_power_w,
                standby_power_w=standby_power_w,
                power_factor_id=power_factor_id,
                unit_id="10208",  # All equipment in synth_data is from 10208 (enac-it)
                equipment_metadata={
                    "source": "synth_data.csv",
                    "imported_at": datetime.utcnow().isoformat(),
                },
            )
            equipment_list.append(equipment_local)
            # equipment_local.unit_id = "12345"
            # equipment_list.append(equipment_local)
    # Bulk insert
    session.add_all(equipment_list)
    await session.commit()

    logger.info(
        f"Created {len(equipment_list)} equipment records: "
        f"{matched_count} matched with power factors, "
        f"{no_match_count} without power factors"
    )

    # Report ambiguous classes that require sub-class selection
    if ambiguous_classes:
        logger.warning(
            f"\n{'=' * 60}\n"
            f"AMBIGUOUS EQUIPMENT CLASSES (Sub-class Required):\n"
            f"{'=' * 60}"
        )
        for eq_class, count in sorted(ambiguous_classes.items()):
            logger.warning(
                f"  - '{eq_class}': {count} equipment item(s) "
                f"(using first match for testing)"
            )
        logger.warning(
            f"{'=' * 60}\n"
            f"Total: {len(ambiguous_classes)} classes, "
            f"{sum(ambiguous_classes.values())} equipment items\n"
            f"Note: These equipment have been assigned a power factor for testing,\n"
            f"but should specify a sub-class for accurate emission calculations.\n"
            f"{'=' * 60}"
        )


async def seed_equipment_emissions(session: AsyncSession) -> None:
    """Calculate and seed emissions for all equipment."""
    logger.info("Calculating and seeding equipment emissions...")

    # Delete existing emissions
    result = await session.exec(select(EquipmentEmission))
    existing_emissions = result.all()

    if existing_emissions:
        logger.info(f"Deleting {len(existing_emissions)} existing emission records...")
        for emission in existing_emissions:
            await session.delete(emission)
        await session.commit()

    # Get emission factor
    ef_result = await session.exec(
        select(EmissionFactor)
        .where(col(EmissionFactor.factor_name) == "swiss_electricity_mix")
        .where(col(EmissionFactor.valid_to).is_(None))  # Current version
    )
    emission_factor = ef_result.one_or_none()
    if not emission_factor:
        logger.error("No emission factor found! Run seed_emission_factors first.")
        return
    if not isinstance(emission_factor, EmissionFactor):
        logger.error("No valid emission factor found! Run seed_emission_factors first.")
        return
    # Get all equipment
    eq_result = await session.exec(select(Equipment))
    equipment_list: List[Equipment] = list(eq_result.all())

    logger.info(f"Calculating emissions for {len(equipment_list)} equipment items...")

    # Get power factors map for lookup
    power_factors_map = {}
    pf_result = await session.exec(select(PowerFactor))
    for pf_ in pf_result.all():
        power_factors_map[pf_.id] = pf_

    # Calculate emissions for each equipment
    emissions_list: List[EquipmentEmission] = []

    for equipment in equipment_list:
        # Get power values - either from equipment or from power factor
        if not isinstance(equipment, Equipment):
            logger.error(f"Invalid equipment record: {equipment}")
            continue
        if (
            equipment.active_power_w is not None
            and equipment.standby_power_w is not None
        ):
            # Use measured values
            active_power_w = equipment.active_power_w
            standby_power_w = equipment.standby_power_w
            power_factor_id = equipment.power_factor_id  # May be None
        elif equipment.power_factor_id:
            # Lookup from power factor
            pf: PowerFactor | None = power_factors_map.get(equipment.power_factor_id)
            if not isinstance(pf, PowerFactor):
                logger.error(
                    f"Invalid power factor record for ID "
                    f"{equipment.power_factor_id} on equipment {equipment.id}"
                )
                continue
            if pf:
                active_power_w = pf.active_power_w
                standby_power_w = pf.standby_power_w
                power_factor_id = pf.id
            else:
                logger.warning(
                    f"Power factor {equipment.power_factor_id} "
                    f"not found for equipment {equipment.id}"
                )
                continue
        else:
            # No power factor assigned - likely requires sub-class selection
            logger.info(
                f"Skipping emissions for equipment {equipment.id} ({equipment.name}): "
                f"No power factor assigned. Class '{equipment.equipment_class}' may "
                f"require sub-class selection."
            )
            continue

        # Prepare equipment data for calculation
        equipment_data = {
            "act_usage_pct": equipment.active_usage_pct or 0,
            "pas_usage_pct": equipment.passive_usage_pct or 0,
            "act_power_w": active_power_w,
            "pas_power_w": standby_power_w,
            "status": equipment.status,
        }

        if (emission_factor.value is None) or (emission_factor.id is None):
            logger.error(
                "Emission factor is missing value or ID! Cannot calculate emissions."
            )
            continue
        # Calculate emissions using the versioned calculation service
        emission_result = calculation_service.calculate_equipment_emission_versioned(
            equipment_data=equipment_data,
            emission_factor=emission_factor.value,
            emission_factor_id=emission_factor.id,
            power_factor_id=power_factor_id,
            formula_version="v1_linear",
        )

        # Create EquipmentEmission record
        assert equipment.id is not None, (
            "Equipment must be saved before creating emission"
        )
        equipment_emission = EquipmentEmission(
            equipment_id=equipment.id,
            annual_kwh=emission_result["annual_kwh"],
            kg_co2eq=emission_result["kg_co2eq"],
            emission_factor_id=emission_result["emission_factor_id"],
            power_factor_id=emission_result["power_factor_id"],
            formula_version=emission_result["formula_version"],
            calculation_inputs=emission_result["calculation_inputs"],
            is_current=True,
        )
        emissions_list.append(equipment_emission)

    # Bulk insert emissions
    session.add_all(emissions_list)
    await session.commit()

    skipped_count = len(equipment_list) - len(emissions_list)
    logger.info(
        f"Created {len(emissions_list)} equipment emission records "
        f"({skipped_count} equipment skipped - no power factor assigned)"
    )

    # Calculate and log summary statistics
    total_kwh = sum(e.annual_kwh for e in emissions_list)
    total_co2 = sum(e.kg_co2eq for e in emissions_list)
    logger.info(f"Total annual consumption: {total_kwh:.2f} kWh")
    logger.info(f"Total annual emissions: {total_co2:.2f} kg CO2eq")


async def main() -> None:
    """Main seed function."""
    logger.info("Starting equipment and emissions seeding...")

    async with SessionLocal() as session:
        await seed_equipment(session)
        await seed_equipment_emissions(session)

    logger.info("Equipment and emissions seeding complete!")


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
