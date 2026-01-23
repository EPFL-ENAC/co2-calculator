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
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal

# from app.models.equipment import Equipment, EquipmentEmission
from app.models.data_entry import DataEntry
from app.models.data_entry_emission import DataEntryEmission
from app.models.data_entry_type import DataEntryTypeEnum
from app.models.emission_type import EmissionTypeEnum
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum

# from app.models.emission_factor import EmissionFactor, PowerFactor
from app.models.unit import Unit
from app.schemas.carbon_report import CarbonReportCreate
from app.services import calculation_service
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.services.unit_service import UnitService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT


CSV_PATH = Path(__file__).parent.parent.parent / "seed_data" / "seed_equipment_data.csv"


async def get_carbon_report_module_id(unit_provider_code: str, year: int) -> int:
    """Generate real carbon_report_module_id based on unit and year."""
    # Get unit by provider code to find unit_id
    current_module_type_id = ModuleTypeEnum.equipment_electric_consumption.value
    async with SessionLocal() as session:
        service = CarbonReportService(session)
        unit_service = UnitService(session)
        unit = await unit_service.get_by_provider_code(unit_provider_code)
        if not unit:
            raise ValueError(f"Unit with provider code {unit_provider_code} not found")
        # Get or create carbon report for unit and year
        carbon_report = await service.get_by_unit_and_year(unit_id=unit.id, year=year)
        if not carbon_report:
            # create carbon report if not exists
            logger.info(
                f"Creating carbon report for unit {unit_provider_code} year {year}"
            )
            carbon_report = await service.create(
                data=CarbonReportCreate(unit_id=unit.id, year=year)
            )
            if not carbon_report:
                raise ValueError(
                    f"Could not create carbon report for unit "
                    f"{unit_provider_code} year {year}"
                )
        # Get carbon_report_module_id for equipment module type
        module_service = CarbonReportModuleService(session)
        carbon_report_module = await module_service.get_module(
            carbon_report_id=carbon_report.id,
            module_type_id=current_module_type_id,
        )
        if not carbon_report_module:
            raise ValueError(
                f"Could not find carbon report module for unit "
                f"{unit_provider_code} year {year} "
                f"and module type {current_module_type_id}"
            )
        return carbon_report_module.id

    return f"{unit_provider_code}:{year}"


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


async def load_power_factors_map(session: AsyncSession) -> Dict[str, Factor]:
    """Load power factors from database into a lookup dictionary."""
    logger.info("Loading power factors from database...")

    result = await session.exec(select(Factor).where(Factor.emission_type_id == 2))
    power_factors_list: List[Factor] = result.all()

    # Create lookup dictionary with multiple key strategies
    power_factors_map = {}

    for pf in power_factors_list:
        # Strategy 1: Full match with sub_class
        if pf.classification:
            key_full = (
                f"{pf.data_entry_type_id}:"
                f"{pf.classification.get('class', '').lower()}:"
                f"{(pf.classification.get('sub_class') or '').lower()}"
            )
            power_factors_map[key_full] = pf

        # Strategy 2: Match without sub_class (fallback)
        key_class = (
            f"{pf.data_entry_type_id}:{pf.classification.get('class', '').lower()}"
        )
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
    equipment_subclass: Optional[str],
    power_factors_map: Dict[str, Factor],
) -> Optional[Factor]:
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
        if normalize_equipment_class(pf.classification.get("class", ""))
        == normalized_class
        and (
            not equipment_subclass
            or pf.classification.get("sub_class", "").lower()
            == equipment_subclass.lower()
        )
    ]
    print("Matches found for class", equipment_class, "subclass", equipment_subclass)
    print(len(matches))
    if len(matches) == 0:
        # No power factor found
        return None
    elif len(matches) == 1:
        # Unambiguous match
        return matches[0]
    else:
        # Ambiguous - multiple matches found
        logger.warning(
            f"Ambiguous power factor lookup for class '{equipment_class}' "
            f"and subclass '{equipment_subclass}': "
            f"{len(matches)} matches found. "
            f"Sub-class selection required for accurate matching."
        )
        # For testing, return first match
        return matches[0]


async def seed_equipment(session: AsyncSession) -> None:
    """Seed equipment from synth_data.csv."""
    logger.info("Seeding equipment from CSV...")

    # Delete existing equipment emissions first (to avoid FK constraint violation)
    result = await session.exec(select(DataEntryEmission))
    existing_emissions = result.all()

    if existing_emissions:
        logger.info(f"Deleting {len(existing_emissions)} existing emission records...")
        for emission in existing_emissions:
            await session.delete(emission)
        await session.commit()

    # Now delete existing equipment
    eq_result = await session.exec(select(DataEntry))
    existing_equipment: List[DataEntry] = list(eq_result.all())

    if existing_equipment:
        logger.info(f"Deleting {len(existing_equipment)} existing equipment records...")
        for equipment in existing_equipment:
            await session.delete(equipment)
        await session.commit()

    # Load power factors for lookup
    power_factors_map = await load_power_factors_map(session)

    # Find the CSV file
    csv_path = CSV_PATH
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    # Read and parse CSV
    equipment_list: List[DataEntry] = []
    matched_count = 0
    no_match_count = 0
    ambiguous_classes: Dict[str, int] = {}  # Track classes requiring sub-class

    # upsert unit ids 10208 and 12345 for testing
    logger.info("Seeding equipment records...")
    unit_service = UnitService(session)
    await unit_service.upsert(
        unit_data=Unit(
            provider_code="12345",
            name="test unit 12345",
        )
    )
    await unit_service.upsert(
        unit_data=Unit(
            provider_code="10208",
            name="enac test 10208",
        )
    )

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            name = row.get("Name 1", "").strip()
            category = row.get("Category", "").strip()
            equipment_class = row.get("Class", "").strip()
            # Find all matching power factors for this class
            all_matches = [
                pf
                for pf in power_factors_map.values()
                if pf.classification.get("class", "").lower() == equipment_class.lower()
            ]

            # If class has multiple power factors,
            # assign first one's sub-class for testing
            if len(all_matches) > 1:
                equipment_subclass = all_matches[0].classification.get("sub_class")
            else:
                equipment_subclass = None

            if not name or not category or not equipment_class:
                logger.warning(f"Skipping row {idx} with missing data: {row}")
                continue

            # Lookup power factor - returns None if not found or ambiguous
            power_factor = lookup_power_factor(
                equipment_class, equipment_subclass, power_factors_map
            )

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
                submodule = power_factor.data_entry_type_id

                # Check if this class has multiple power factors (ambiguous)
                all_matches = [
                    pf
                    for pf in power_factors_map.values()
                    if pf.classification.get("class", "").lower()
                    == equipment_class.lower()
                ]
                if len(all_matches) > 1:
                    ambiguous_classes[equipment_class] = (
                        ambiguous_classes.get(equipment_class, 0) + 1
                    )

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

            # for 10208 and 12345 units for year 2025
            carbon_report_module_id_10208 = await get_carbon_report_module_id(
                unit_provider_code="10208", year=2025
            )
            equipment_local_10208 = DataEntry(
                data_entry_type_id=submodule,
                carbon_report_module_id=carbon_report_module_id_10208,
                data={
                    "active_usage_hours": active_usage_pct,
                    "passive_usage_hours": passive_usage_pct,
                    "name": name,
                    "power_factor_id": power_factor_id,
                },
            )

            carbon_report_module_id_12345 = await get_carbon_report_module_id(
                unit_provider_code="12345", year=2025
            )
            equipment_local_12345 = DataEntry(
                data_entry_type_id=submodule,
                carbon_report_module_id=carbon_report_module_id_12345,
                data={
                    "active_usage_hours": active_usage_pct,
                    "passive_usage_hours": passive_usage_pct,
                    "power_factor_id": power_factor_id,
                },
            )

            # cost_center=cost_center,
            # cost_center_description=cost_center_desc or None,
            # "name": name,
            # category=category,
            # submodule=submodule,
            # equipment_class=equipment_class,
            # sub_class=equipment_subclass,
            # service_date=service_date,
            # status=status,
            # active_usage_pct=active_usage_pct,
            # passive_usage_pct=passive_usage_pct,
            # active_power_w=active_power_w,
            # standby_power_w=standby_power_w,
            # power_factor_id=power_factor_id,
            # unit_id=unit_test_10208.id,
            # equipment_metadata={
            #     "source": "synth_data.csv",
            #     "imported_at": datetime.utcnow().isoformat(),
            # },
            equipment_list.append(equipment_local_10208)
            equipment_list.append(equipment_local_12345)
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
    result = await session.exec(select(DataEntryEmission))
    existing_emissions = result.all()

    if existing_emissions:
        logger.info(f"Deleting {len(existing_emissions)} existing emission records...")
        for emission in existing_emissions:
            await session.delete(emission)
        await session.commit()

    # Get emission factor
    ef_result = await session.exec(
        select(Factor).where(col(Factor.emission_type_id) == EmissionTypeEnum.energy)
    )
    emission_factor = ef_result.one_or_none()
    if not emission_factor:
        logger.error("No emission factor found! Run seed_emission_factors first.")
        return
    if not isinstance(emission_factor, Factor):
        logger.error("No valid emission factor found! Run seed_emission_factors first.")
        return
    # Get all equipment
    eq_result = await session.exec(select(DataEntry))
    equipment_list: List[DataEntry] = list(eq_result.all())

    logger.info(f"Calculating emissions for {len(equipment_list)} equipment items...")

    # Get power factors map for lookup
    power_factors_map = {}
    pf_result = await session.exec(
        select(Factor).where(col(Factor.emission_type_id) == EmissionTypeEnum.equipment)
    )
    for pf_ in pf_result.all():
        power_factors_map[pf_.id] = pf_

    # Calculate emissions for each equipment
    emissions_list: List[DataEntryEmission] = []

    for equipment in equipment_list:
        # Get power values - either from equipment or from power factor
        if not isinstance(equipment, DataEntry):
            logger.error(f"Invalid equipment record: {equipment}")
            continue

        if equipment.data.get("power_factor_id"):
            # Lookup from power factor
            pf: Factor | None = power_factors_map.get(
                equipment.data.get("power_factor_id")
            )
            if not isinstance(pf, Factor):
                logger.error(
                    f"Invalid power factor record for ID "
                    f"{equipment.power_factor_id} on equipment {equipment.id}"
                )
                continue
            if pf:
                power_factor_id = pf.id
                active_power_w = pf.values.get("active_power_w", 0) or 0
                standby_power_w = pf.values.get("standby_power_w", 0) or 0
            else:
                logger.warning(f"not found for equipment {equipment.id}")
                continue
        else:
            # No power factor assigned - likely requires sub-class selection
            logger.info(
                f"Skipping emissions for data entry {equipment.id} ({equipment.name}): "
                f"require sub-class selection."
            )
            continue

        # Prepare equipment data for calculation
        equipment_data = {
            "active_usage_hours": equipment.data.get("active_usage_hours") or 0,
            "passive_usage_hours": equipment.data.get("passive_usage_hours") or 0,
        }

        if (emission_factor.values is None) or (emission_factor.id is None):
            logger.error(
                "Emission factor is missing value or ID! Cannot calculate emissions."
            )
            continue
        mix_energy = emission_factor.values.get("kgco2eq_per_kwh", None)
        if mix_energy is None:
            raise ValueError("Emission factor missing 'kgco2eq_per_kwh' value")
        # Calculate emissions using the versioned calculation service
        emission_result = calculation_service.calculate_equipment_emission(
            equipment_data=equipment_data,
            emission_electric_factor=mix_energy,
            active_power_w=active_power_w,
            standby_power_w=standby_power_w,
        )

        # Create EquipmentEmission record
        assert equipment.id is not None, (
            "Equipment must be saved before creating emission"
        )
        equipment_emission = DataEntryEmission(
            data_entry_id=equipment.id,
            emission_type_id=EmissionTypeEnum.equipment,
            primary_factor_id=power_factor_id,
            subcategory=DataEntryTypeEnum(
                equipment.data_entry_type_id
            ).name.title(),  # TODO: should be an enum somwhere
            kg_co2eq=emission_result["kg_co2eq"],
            meta={
                "annual_kwh": emission_result["annual_kwh"],
                "calculation_inputs": equipment.data,
                "emission_factor_id": emission_factor.id,
                # "power_factor_id": emission_result["power_factor_id"],
                # "formula_version": emission_result["formula_version"],
            },
            formula_version=versionapi,
            computed_at=datetime.now(timezone.utc),
        )
        emissions_list.append(equipment_emission)

    # Bulk insert emissions
    session.add_all(emissions_list)
    await session.commit()

    skipped_count = len(equipment_list) - len(emissions_list)
    logger.info(
        f"Created {len(emissions_list)} data entry emission records "
        f"({skipped_count} data entries skipped - no power factor assigned)"
    )

    # Calculate and log summary statistics
    total_kwh = sum(e.meta.get("annual_kwh", 0) for e in emissions_list)
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
