"""Generic CSV-based data entry seeder with emission computation.

Reads ``seed_data_clean/*_data.csv`` files, creates DataEntry rows,
resolves factors via kind/subkind, and computes emissions through the
standard ``DataEntryEmissionService`` pipeline.
"""

import asyncio
import csv
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

# Ensure all handlers are registered before use
import app.modules.buildings.schemas as _b  # noqa: F401
import app.modules.equipment_electric_consumption.schemas as _eq  # noqa: F401
import app.modules.external_cloud_and_ai.schemas as _ec  # noqa: F401
import app.modules.headcount.schemas as _hc  # noqa: F401
import app.modules.process_emissions.schemas as _pe  # noqa: F401
import app.modules.professional_travel.schemas as _pt  # noqa: F401
import app.modules.purchase.schemas as _pu  # noqa: F401
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import BaseModuleHandler
from app.seed.seed_helper import (
    get_carbon_report_module_id,
    load_factors_map,
    lookup_factor,
)
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService

logger = get_logger(__name__)
settings = get_settings()

SEED_FOLDER = Path(__file__).parent.parent.parent / "seed_data_clean"
YEAR = 2025
EXCLUDE_COLUMNS = {"unit_institutional_id", "kg_co2eq"}


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
    # DataEntrySeedConfig(
    #     path=SEED_FOLDER / "researchfacilities_common_data.csv",
    #     data_entry_types=[DataEntryTypeEnum.research_facilities],
    #     module_type=ModuleTypeEnum.internal_services,
    # ),
    # DataEntrySeedConfig(
    #     path=SEED_FOLDER / "researchfacilities_animals_data.csv",
    #     data_entry_types=[DataEntryTypeEnum.mice_and_fish_animal_facilities],
    #     module_type=ModuleTypeEnum.internal_services,
    # ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_value(value: str) -> str | int | float | None:
    """Try to convert a CSV string to int or float, falling back to str."""
    if value == "":
        return None
    try:
        f = float(value)
        if f == int(f) and "." not in value:
            return int(f)
        return f
    except (ValueError, OverflowError):
        return value


async def _resolve_location_id(
    session: AsyncSession,
    code: str,
    transport_mode: TransportModeEnum,
) -> int | None:
    """Resolve an IATA code or station name to a location ID."""
    code = code.strip()
    if not code:
        return None

    if transport_mode == TransportModeEnum.plane:
        stmt = select(col(Location.id)).where(
            col(Location.iata_code) == code.upper(),
            col(Location.transport_mode) == transport_mode,
        )
    else:
        stmt = select(col(Location.id)).where(
            col(Location.name).ilike(code),
            col(Location.transport_mode) == transport_mode,
        )

    location_id = (await session.execute(stmt)).scalar_one_or_none()
    if location_id is None:
        logger.warning("Location not found: '%s' (mode=%s)", code, transport_mode.value)
    return location_id


async def _resolve_type_from_factors(
    kind: str,
    subkind: str | None,
    data_entry_types: list[DataEntryTypeEnum],
    factors_cache: dict[DataEntryTypeEnum, dict],
) -> DataEntryTypeEnum | None:
    """Resolve data_entry_type by finding which type's factors match."""
    for det in data_entry_types:
        fmap = factors_cache.get(det, {})
        factor = lookup_factor(kind, subkind, fmap)
        if factor is not None:
            return det
    return None


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------


async def seed_data_entries(
    session: AsyncSession,
    config: DataEntrySeedConfig,
) -> None:
    """Seed data entries from a CSV and compute their emissions."""
    if not config.path.exists():
        logger.warning("CSV not found, skipping: %s", config.path)
        return

    service = DataEntryService(session)

    # Caches
    crm_cache: dict[str, int] = {}
    factors_cache: dict[DataEntryTypeEnum, dict] = {}

    # Pre-load factor maps for types that use kind-based lookup
    for det in config.data_entry_types:
        handler = BaseModuleHandler.get_by_type(det)
        if handler.kind_field:
            factors_cache[det] = await load_factors_map(session, det)

    # Resolve data_entry_type helpers
    det_column = config.data_entry_type_column
    name_to_enum = {det.name: det for det in config.data_entry_types}
    fixed_type = (
        config.data_entry_types[0]
        if len(config.data_entry_types) == 1 and not det_column
        else None
    )
    multi_type_from_factor = len(config.data_entry_types) > 1 and det_column is None

    data_entries: list[DataEntry] = []
    skipped = 0
    unknown_kind = set()
    unknown_cf = set()
    # for debug: TO REMOVE BEFORE COMMIT
    # max_rows = 10  # safety limit to avoid runaway seeds
    with open(config.path, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # if len(data_entries) >= max_rows:
            #     break
            # --- resolve data_entry_type ---
            if det_column:
                det_name = row.get(det_column, "").strip()
                data_entry_type = name_to_enum.get(det_name)
                if data_entry_type is None:
                    logger.warning(
                        "Unknown data_entry_type '%s' in %s",
                        det_name,
                        config.path.name,
                    )
                    skipped += 1
                    continue
            elif fixed_type:
                data_entry_type = fixed_type
            else:
                # Will resolve later from factor match
                data_entry_type = None

            # --- resolve carbon_report_module_id ---
            unit_code = row.get("unit_institutional_id", "").strip()
            if unit_code:
                unit_code = unit_code.zfill(4)
            if not unit_code:
                skipped += 1
                continue

            if unit_code not in crm_cache:
                try:
                    crm_cache[unit_code] = await get_carbon_report_module_id(
                        unit_code, YEAR, config.module_type
                    )
                except ValueError as exc:
                    logger.warning("%s", exc)
                    unknown_cf.add(unit_code)
                    skipped += 1
                    continue

            # --- build data dict from CSV columns ---
            data: dict[str, str | int | float | None] = {}
            handler = (
                BaseModuleHandler.get_by_type(data_entry_type)
                if data_entry_type
                else BaseModuleHandler.get_by_type(config.data_entry_types[0])
            )
            for csv_col, val in row.items():
                if csv_col in EXCLUDE_COLUMNS:
                    continue
                if det_column and csv_col == det_column:
                    continue

                # Location resolution for travel
                if config.location_fields and csv_col in config.location_fields:
                    assert config.transport_mode is not None
                    loc_id = await _resolve_location_id(
                        session, val, config.transport_mode
                    )
                    data[config.location_fields[csv_col]] = loc_id
                    continue

                data[csv_col] = _coerce_value(val)

            # --- factor lookup ---
            kind_field = handler.kind_field
            subkind_field = handler.subkind_field

            if kind_field:
                kind_val = str(data.get(kind_field, ""))
                subkind_raw = data.get(subkind_field, None) if subkind_field else None
                subkind_val = None
                if subkind_raw is not None:
                    subkind_val = str(subkind_raw)
                # Multi-type without column: resolve from factor
                if multi_type_from_factor and data_entry_type is None:
                    data_entry_type = await _resolve_type_from_factors(
                        kind_val,
                        subkind_val,
                        config.data_entry_types,
                        factors_cache,
                    )
                    if data_entry_type is None:
                        data_entry_type = config.data_entry_types[0]
                        logger.warning(
                            "No factor match for kind='%s' — defaulting to %s",
                            kind_val,
                            data_entry_type.name,
                        )
                        unknown_kind.add(kind_val)

                fmap = factors_cache.get(
                    data_entry_type or config.data_entry_types[0],
                    {},
                )
                factor = lookup_factor(kind_val, subkind_val, fmap)
                data["primary_factor_id"] = factor.id if factor else None
                # update from factor with generic handler for csv upload
                if factor and handler.factor_value_fields:
                    for field_name in handler.factor_value_fields:
                        if field_name not in data or data[field_name] in (None, "", 0):
                            data[field_name] = factor.values.get(field_name)
                # Derive type from factor when still unknown
                if multi_type_from_factor and factor and factor.data_entry_type_id:
                    matched = DataEntryTypeEnum(factor.data_entry_type_id)
                    if matched in config.data_entry_types:
                        data_entry_type = matched
            # Fallback if type still not resolved
            if data_entry_type is None:
                data_entry_type = config.data_entry_types[0]

            entry = DataEntry(
                carbon_report_module_id=crm_cache[unit_code],
                data_entry_type_id=data_entry_type.value,
                data=data,
            )
            entry.data_entry_type = data_entry_type
            data_entries.append(entry)

    if not data_entries:
        logger.warning(
            "No data entries produced from %s (skipped=%d)",
            config.path.name,
            skipped,
        )
        return

    # Bulk create data entries
    responses = await service.bulk_create(data_entries)
    await session.commit()

    # Compute and create emissions
    emission_service = DataEntryEmissionService(session)
    emissions: list = []
    for resp in responses:
        objs = await emission_service.prepare_create(resp)
        if objs:
            emissions.extend(objs)

    if emissions:
        await emission_service.bulk_create(emissions)
        await session.commit()

    label = ", ".join(det.name for det in config.data_entry_types)
    print(
        f"Created {len(data_entries)} entries + "
        f"{len(emissions)} emissions for [{label}]"
    )
    print(f"    Unknown kinds: {list(unknown_kind)}") if unknown_kind else None
    print(f"    Unknown cf ids: {list(unknown_cf)}") if unknown_cf else None
    if skipped:
        print(f"  ({skipped} rows skipped)")
    logger.info(
        "Seeded %d entries + %d emissions from %s",
        len(data_entries),
        len(emissions),
        config.path.name,
    )


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
