import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import get_module_type_for_data_entry_type
from app.modules.external_cloud_and_ai import (
    schemas as schemas,
)  # This ensures the handlers are registered
from app.modules.process_emissions import (
    schemas as _pe_schemas,  # noqa: F401 — registers handlers
)
from app.modules.purchase import (
    schemas as _purchase_schemas,  # noqa: F401 — registers handlers
)
from app.modules.research_facilities import (
    animals_schemas as _rf_animals_schemas,  # noqa: F401 — registers handlers
)
from app.modules.research_facilities import (
    common_schemas as _rf_common_schemas,  # noqa: F401 — registers handlers
)
from app.schemas.factor import BaseFactorHandler
from app.services.data_ingestion.csv_providers.local_seed import LocalFactorCSVProvider

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT

BACKEND_FOLDER = Path(__file__).parent.parent.parent / "seed_data"
YEAR = 2025


@dataclass
class FactorSeedConfig:
    """Configuration for seeding factors from a CSV file.

    When data_entry_type_column is None, all rows use the single type
    in data_entry_types. When set, the column value is used to resolve
    the DataEntryTypeEnum per row.
    """

    path: Path
    data_entry_types: list[DataEntryTypeEnum] = field(default_factory=list)
    data_entry_type_column: str | None = None


# building_energycombustions_factors.csv
# building_rooms_factors.csv
# commuting_factors.csv
# equipments_factors.csv
# external_ai_factors.csv
# external_clouds_factors.csv
# food_factors.csv
# headcount_member_factors.csv
# headcount_students_factors.csv
# processemissions_factors.csv
# purchases_additional_factors.csv
# purchases_common_factors.csv
# researchfacilities_animals_factors.csv
# researchfacilities_common_factors.csv
# travel_planes_factors.csv
# travel_trains_factors.csv
# waste_factors.csv
FACTOR_SEEDS: list[FactorSeedConfig] = [
    FactorSeedConfig(
        path=BACKEND_FOLDER / "building_energycombustions_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.energy_combustion,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "building_rooms_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.building,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "buildings_greyenergy_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.building_embodied_energy,
        ],
    ),
    # FactorSeedConfig(
    #     path=BACKEND_FOLDER / "commuting_factors.csv", data_entry_types=[]
    # ),
    # Multi data_entry_type CSV — column differentiates (other, it, scientific)
    FactorSeedConfig(
        path=BACKEND_FOLDER / "equipments_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.scientific,
            DataEntryTypeEnum.it,
            DataEntryTypeEnum.other,
        ],
        data_entry_type_column="equipment_category",
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "external_ai_factors.csv",
        data_entry_types=[DataEntryTypeEnum.external_ai],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "external_clouds_factors.csv",
        data_entry_types=[DataEntryTypeEnum.external_clouds],
    ),
    # FactorSeedConfig(path=BACKEND_FOLDER / "food_factors.csv", data_entry_types=[]),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "headcount_member_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.member,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "headcount_students_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.student,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "processemissions_factors.csv",
        data_entry_types=[DataEntryTypeEnum.process_emissions],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "purchases_additional_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.additional_purchases,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "purchases_common_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.scientific_equipment,
            DataEntryTypeEnum.it_equipment,
            DataEntryTypeEnum.consumable_accessories,
            DataEntryTypeEnum.biological_chemical_gaseous_product,
            DataEntryTypeEnum.services,
            DataEntryTypeEnum.vehicles,
            DataEntryTypeEnum.other_purchases,
        ],
        data_entry_type_column="purchase_category",
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "researchfacilities_animals_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.mice_and_fish_animal_facilities,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "researchfacilities_common_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.research_facilities,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "travel_planes_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.plane,
        ],
    ),
    FactorSeedConfig(
        path=BACKEND_FOLDER / "travel_trains_factors.csv",
        data_entry_types=[
            DataEntryTypeEnum.train,
        ],
    ),
    # FactorSeedConfig(path=BACKEND_FOLDER / "waste_factors.csv", data_entry_types=[]),
]


async def seed_factors(session: AsyncSession, config: FactorSeedConfig) -> None:
    """Seed factors from a CSV using the ingestion pipeline."""
    if not config.data_entry_types:
        raise ValueError("At least one data_entry_type must be provided")
    first_type = config.data_entry_types[0]
    module_type = get_module_type_for_data_entry_type(first_type)
    if module_type is None:
        raise ValueError(
            f"Cannot determine module_type for data_entry_type: {first_type.name}"
        )

    if config.data_entry_type_column is not None:
        for det in config.data_entry_types:
            handler = BaseFactorHandler.get_by_type(det)
            actual = getattr(handler, "category_field", None)
            if actual != config.data_entry_type_column:
                raise ValueError(
                    f"data_entry_type_column={config.data_entry_type_column!r} "
                    f"does not match "
                    f"{type(handler).__name__}.category_field={actual!r} "
                    f"for data_entry_type={det.name}"
                )

    provider_config: dict = {
        "local_file_path": str(config.path),
        "module_type_id": module_type.value,
        "year": YEAR,
        "data_entry_type_id": (
            config.data_entry_types[0].value
            if config.data_entry_type_column is None
            else None
        ),
        "explicit_entry_type_ids": [det.value for det in config.data_entry_types],
    }

    provider = LocalFactorCSVProvider(config=provider_config, data_session=session)
    result = await provider.process_csv_in_batches()

    label = ", ".join(det.name for det in config.data_entry_types)
    inserted = result.get("inserted", 0)
    skipped = result.get("skipped", 0)
    print(f"Created {inserted} factors for [{label}] ({skipped} skipped)")
    await session.commit()
    logger.info(f"Seeded factors for [{label}].")


async def main() -> None:
    """Main seed function."""

    async with SessionLocal() as session:
        for config in FACTOR_SEEDS:
            await seed_factors(session, config)


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
