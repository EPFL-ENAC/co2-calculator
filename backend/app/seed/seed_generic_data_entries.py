"""Generic CSV-based data entry seeder with emission computation.

Reads ``seed_data/*_data.csv`` files and delegates the full ingestion
pipeline (factor lookup, batch inserts, emission computation, stats
recomputation) to ``LocalDataEntryCSVProvider``.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.location import TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.csv_providers.local_seed import (
    LocalDataEntryCSVProvider,
)

logger = get_logger(__name__)

SEED_FOLDER = Path(__file__).parent.parent.parent / "seed_data"
YEAR = 2025


@dataclass
class DataEntrySeedConfig:
    """Configuration for seeding data entries from a CSV file.

    When *data_entry_type_column* is ``None`` and a single type is given
    in *data_entry_types*, every row uses that fixed type.  When the
    column is set the value is used to resolve the type per row.
    When multiple types are given **without** a column, the type is
    derived from the matched factor's ``data_entry_type_id``.

    For travel CSVs set *location_fields* to map CSV columns (e.g.
    ``"from"``) to data-dict keys (e.g. ``"origin_location_id"``),
    together with the matching *transport_mode*.
    """

    path: Path
    data_entry_types: list[DataEntryTypeEnum] = field(default_factory=list)
    module_type: ModuleTypeEnum = ModuleTypeEnum.headcount
    data_entry_type_column: str | None = None
    location_fields: dict[str, str] | None = None
    transport_mode: TransportModeEnum | None = None


# ---------------------------------------------------------------------------
# Seed configurations — one entry per CSV
# ---------------------------------------------------------------------------

DATA_ENTRY_SEEDS: list[DataEntrySeedConfig] = [
    DataEntrySeedConfig(
        path=SEED_FOLDER / "external_clouds_data.csv",
        data_entry_types=[DataEntryTypeEnum.external_clouds],
        module_type=ModuleTypeEnum.external_cloud_and_ai,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "external_ai_data.csv",
        data_entry_types=[DataEntryTypeEnum.external_ai],
        module_type=ModuleTypeEnum.external_cloud_and_ai,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "processemissions_data.csv",
        data_entry_types=[DataEntryTypeEnum.process_emissions],
        module_type=ModuleTypeEnum.process_emissions,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "building_energycombustions_data.csv",
        data_entry_types=[DataEntryTypeEnum.energy_combustion],
        module_type=ModuleTypeEnum.buildings,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "equipments_data.csv",
        data_entry_types=[
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.other,
        ],
        module_type=ModuleTypeEnum.equipment_electric_consumption,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "headcount_data.csv",
        data_entry_types=[DataEntryTypeEnum.member],
        module_type=ModuleTypeEnum.headcount,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "purchases_common_data.csv",
        data_entry_types=[
            DataEntryTypeEnum.scientific_equipment,
            DataEntryTypeEnum.it_equipment,
            DataEntryTypeEnum.consumable_accessories,
            DataEntryTypeEnum.biological_chemical_gaseous_product,
            DataEntryTypeEnum.services,
            DataEntryTypeEnum.vehicles,
            DataEntryTypeEnum.other_purchases,
        ],
        module_type=ModuleTypeEnum.purchase,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "purchases_additional_data.csv",
        data_entry_types=[DataEntryTypeEnum.additional_purchases],
        module_type=ModuleTypeEnum.purchase,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "travel_planes_data.csv",
        data_entry_types=[DataEntryTypeEnum.plane],
        module_type=ModuleTypeEnum.professional_travel,
        location_fields={
            "from": "origin_location_id",
            "to": "destination_location_id",
        },
        transport_mode=TransportModeEnum.plane,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "travel_trains_data.csv",
        data_entry_types=[DataEntryTypeEnum.train],
        module_type=ModuleTypeEnum.professional_travel,
        location_fields={
            "from": "origin_location_id",
            "to": "destination_location_id",
        },
        transport_mode=TransportModeEnum.train,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "building_rooms_data.csv",
        data_entry_types=[DataEntryTypeEnum.building],
        module_type=ModuleTypeEnum.buildings,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "researchfacilities_common_data.csv",
        data_entry_types=[DataEntryTypeEnum.research_facilities],
        module_type=ModuleTypeEnum.research_facilities,
    ),
    DataEntrySeedConfig(
        path=SEED_FOLDER / "researchfacilities_animals_data.csv",
        data_entry_types=[DataEntryTypeEnum.mice_and_fish_animal_facilities],
        module_type=ModuleTypeEnum.research_facilities,
    ),
]


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------


async def seed_data_entries(
    session: AsyncSession,
    config: DataEntrySeedConfig,
) -> None:
    """Seed data entries from a CSV using the standard ingestion pipeline."""
    if not config.path.exists():
        logger.warning("CSV not found, skipping: %s", config.path)
        return

    provider_config: dict = {
        "local_file_path": str(config.path),
        "module_type_id": config.module_type.value,
        "year": YEAR,
        "data_entry_type_id": (
            config.data_entry_types[0].value
            if len(config.data_entry_types) == 1
            else None
        ),
        "location_fields": config.location_fields,
        "transport_mode_value": (
            config.transport_mode.value if config.transport_mode else None
        ),
    }
    provider = LocalDataEntryCSVProvider(config=provider_config, data_session=session)
    result = await provider.process_csv_in_batches()

    label = ", ".join(det.name for det in config.data_entry_types)
    print(
        f"Created {result['inserted']} entries for [{label}]"
        + (f" ({result['skipped']} skipped)" if result["skipped"] else "")
    )
    await session.commit()
    logger.info("Seeded data entries for [%s].", label)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------



async def main() -> None:
    """Run all configured data-entry seeds."""
    async with SessionLocal() as session:
        for config in DATA_ENTRY_SEEDS:
            await seed_data_entries(session, config)


if __name__ == "__main__":
    asyncio.run(main())
