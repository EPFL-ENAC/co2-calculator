import asyncio
import csv
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
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
    schemas as _rf_schemas,  # noqa: F401 — registers handlers
)
from app.schemas.factor import BaseFactorHandler
from app.seed.seed_helper import (
    get_factor_emission_type_id,
)
from app.services.factor_service import FactorService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT

BACKEND_FOLDER = Path(__file__).parent.parent.parent / "seed_data"


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


def get_float_or_none(value: str | None) -> float | None:
    """Convert string to float or return None if empty."""
    if value is None or value == "":
        return None
    return float(value)


async def seed_factors(session: AsyncSession, config: FactorSeedConfig) -> None:
    """Seed factors from a CSV according to the given config."""
    service = FactorService(session)

    for det in config.data_entry_types:
        await service.bulk_delete_by_data_entry_type(det)

    name_to_enum = {det.name: det for det in config.data_entry_types}
    det_column = config.data_entry_type_column
    fixed_type = config.data_entry_types[0] if not det_column else None

    def resolve(row: dict) -> DataEntryTypeEnum | None:
        if det_column:
            det_name = row.get(det_column, "").strip()
            det = name_to_enum.get(det_name)
            if det is None:
                logger.warning(
                    f"Unknown data_entry_type '{det_name}' in CSV row {row},"
                    f" expected one of {list(name_to_enum.keys())}"
                )
            return det
        return fixed_type

    factors = []
    with open(config.path, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data_entry_type = resolve(row)
            if data_entry_type is None:
                continue

            handler = BaseFactorHandler.get_by_type(data_entry_type)
            emission_type_id = get_factor_emission_type_id(data_entry_type, row)
            required = handler.required_columns

            classification = {}
            for field_name in handler.classification_fields:
                if not row.get(field_name) and field_name in required:
                    logger.warning(
                        f"Missing required classification field '{field_name}'"
                        f" for {data_entry_type.name} factor: {row}"
                    )
                classification[field_name] = row.get(field_name) or None

            values: dict[str, float | int | str | None] = {}
            for field_name in handler.value_fields:
                if not row.get(field_name) and field_name in required:
                    logger.warning(
                        f"Missing required value field '{field_name}'"
                        f" for {data_entry_type.name} factor: {row}"
                    )
                value = row.get(field_name)
                # Normalize whitespace from CSV; keep empty as None.
                if isinstance(value, str):
                    value = value.strip()
                # Convert to float if it is not alphabetical
                # (e.g., for currency we keep as string)
                values[field_name] = (
                    get_float_or_none(value)
                    if value and not value.isalpha()
                    else value or None
                )

            factor = await service.prepare_create(
                emission_type_id=emission_type_id,
                is_conversion=False,
                data_entry_type_id=data_entry_type.value,
                classification=classification,
                values=values,
            )
            factors.append(factor)

    await service.bulk_create(factors)
    label = ", ".join(det.name for det in config.data_entry_types)
    print(f"Created {len(factors)} factors for [{label}]")
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
