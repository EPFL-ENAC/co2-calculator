import asyncio
import csv
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.modules.purchase import (
    schemas as schemas,
)  # This ensures the handlers are registered
from app.seed.seed_helper import (
    get_carbon_report_module_id,
    load_factors_map,
    lookup_factor,
)
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.factor_service import FactorService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT

CSV_PATH_COMMON_FACTOR = (
    Path(__file__).parent.parent.parent / "seed_data" / "purchases_common_factors.csv"
)

CSV_PATH_COMMON_DATA = (
    Path(__file__).parent.parent.parent / "seed_data" / "purchases_common_data.csv"
)

CSV_PATH_ADDITIONAL_FACTOR = (
    Path(__file__).parent.parent.parent
    / "seed_data"
    / "purchases_additional_factors.csv"
)

CSV_PATH_ADDITIONAL_DATA = (
    Path(__file__).parent.parent.parent / "seed_data" / "purchases_additional_data.csv"
)


def get_float_or_none(value: str | None) -> float | None:
    """Convert string to float or return None if empty."""
    if value is None:
        return None

    if value == "":
        return None
    return float(value)


async def seed_factor_commons(session: AsyncSession, entry_type: str) -> None:
    """Seed factors for External Cloud.
    1. bulk delete factors
    2. bulk insert factors
    """
    service = FactorService(session)
    factors = []
    # 1. bulk delete factors
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum[entry_type])
    with open(CSV_PATH_COMMON_FACTOR, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            purchase_category = row.get("purchase_category", "")
            if (
                purchase_category == ""
                or purchase_category.lower() != entry_type.lower()
            ):
                continue
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum[f"purchase_{entry_type}"],
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum[entry_type],
                classification={
                    "purchase_institutional_code": row.get(
                        "purchase_institutional_code", ""
                    ),
                    "purchase_institutional_description": row.get(
                        "purchase_institutional_description", ""
                    ),
                    "purchase_category": row.get("purchase_category", ""),
                    "purchase_additional_code": row.get("purchase_additional_code", ""),
                    "kind": row.get("purchase_institutional_code", ""),
                },
                values={
                    "currency": row.get("currency", "eur").lower(),
                    "ef_kg_co2eq_per_currency": get_float_or_none(
                        row.get("ef_kg_co2eq_per_currency")
                    ),
                },
            )
            factors.append(factor)
    await service.bulk_create(factors)
    print(f"Created {len(factors)} Purchase Common factors for {entry_type}")
    await session.commit()
    logger.info(f"Seeded Purchase Common factors for {entry_type}")


async def seed_factor_additional(session: AsyncSession) -> None:
    service = FactorService(session)
    factors = []
    # 1. bulk delete factors
    await service.bulk_delete_by_data_entry_type(DataEntryTypeEnum.additional_purchases)
    with open(CSV_PATH_ADDITIONAL_FACTOR, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            factor = await service.prepare_create(
                emission_type_id=EmissionTypeEnum.purchase_additional_purchases,
                is_conversion=False,
                data_entry_type_id=DataEntryTypeEnum.additional_purchases,
                classification={
                    "name": row.get("name"),
                    "note": row.get("note", ""),
                    "kind": row.get("name", ""),
                },
                values={
                    "ef_kg_co2eq_per_kg": get_float_or_none(
                        row.get("ef_kg_co2eq_per_kg")
                    ),
                },
            )
            factors.append(factor)
    await service.bulk_create(factors)
    print(f"Created {len(factors)} Purchase Additional factors")
    await session.commit()
    logger.info("Seeded Purchase Additional factors.")


async def seed_data_commons(
    session: AsyncSession, entry_type: str, carbon_report_module_id: int
) -> None:
    service = DataEntryService(session)
    data_entries = []
    #  bulk delete data entries
    await service.bulk_delete(carbon_report_module_id, DataEntryTypeEnum[entry_type])

    factors_map = await load_factors_map(session, DataEntryTypeEnum[entry_type])

    with open(CSV_PATH_COMMON_DATA, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            kind = row.get("purchase_institutional_code", "")
            subkind = ""
            factor = lookup_factor(kind, subkind, factors_map)
            data_entry = DataEntry(
                carbon_report_module_id=carbon_report_module_id,
                data={
                    "primary_factor_id": factor.id if factor else None,
                    "name": row.get("name", ""),
                    "total_spent_amount": float(row.get("total_spent_amount", 0)),
                    "purchase_institutional_code": row.get(
                        "purchase_institutional_code", ""
                    ),
                    "supplier": row.get("supplier", ""),
                    "quantity": float(row.get("quantity", 0)),
                    "currency": row.get("currency", "").lower(),
                    "purchase_additional_code": row.get("purchase_additional_code", ""),
                },
            )
            data_entry.data_entry_type = DataEntryTypeEnum[entry_type]
            data_entries.append(data_entry)
    # 1. Bulk create all data entries first
    data_entries_response = await service.bulk_create(data_entries)
    print(
        f"Created {len(data_entries_response)} Purchase Common data entries for "
        f"{entry_type}"
    )
    await session.commit()

    # 2. Now, create the emissions for all of them using the service logic
    emissions_to_create = []
    emission_service = DataEntryEmissionService(session)

    for data_entry_response in data_entries_response:
        emission_obj = await emission_service.prepare_create(data_entry_response)
        if emission_obj is not None:
            emissions_to_create.append(emission_obj)

    # 3. Bulk create the emissions
    await emission_service.bulk_create(emissions_to_create)

    # 4. ONE final commit for the entire seed batch
    print(
        f"Calculated {len(emissions_to_create)} Purchase Common emissions for "
        f"{entry_type}"
    )
    await session.commit()
    logger.info(f"Seeded Common Purchase data entries for {entry_type}.")


async def seed_data_additional(
    session: AsyncSession, carbon_report_module_id: int
) -> None:
    service = DataEntryService(session)
    data_entries = []
    #  bulk delete data entries
    await service.bulk_delete(
        carbon_report_module_id, DataEntryTypeEnum.additional_purchases
    )

    factors_map = await load_factors_map(
        session, DataEntryTypeEnum.additional_purchases
    )

    with open(CSV_PATH_ADDITIONAL_DATA, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            kind = row.get("name", "")
            subkind = ""
            factor = lookup_factor(kind, subkind, factors_map)
            data_entry = DataEntry(
                carbon_report_module_id=carbon_report_module_id,
                data={
                    "primary_factor_id": factor.id if factor else None,
                    "name": row.get("name", ""),
                    "unit": row.get("unit", ""),
                    "annual_consumption": float(row.get("annual_consumption", 0)),
                    "coef_to_kg": float(row.get("coef_to_kg", 0)),
                    "note": row.get("note", ""),
                },
            )
            data_entry.data_entry_type = DataEntryTypeEnum.additional_purchases
            data_entries.append(data_entry)
    # 1. Bulk create all data entries first
    data_entries_response = await service.bulk_create(data_entries)
    print(f"Created {len(data_entries_response)} Purchase Additional data entries")
    await session.commit()

    # 2. Now, create the emissions for all of them using the service logic
    emissions_to_create = []
    emission_service = DataEntryEmissionService(session)

    for data_entry_response in data_entries_response:
        emission_obj = await emission_service.prepare_create(data_entry_response)
        if emission_obj is not None:
            emissions_to_create.append(emission_obj)

    # 3. Bulk create the emissions
    await emission_service.bulk_create(emissions_to_create)

    # 4. ONE final commit for the entire seed batch
    print(f"Calculated {len(emissions_to_create)} Purchase Additional emissions")
    await session.commit()
    logger.info("Seeded Additional Purchase data entries.")


async def main():
    logger.info("Starting purchase data seeding...")

    async with SessionLocal() as session:
        await seed_factor_commons(session, "scientific_equipment")
        await seed_factor_commons(session, "it_equipment")
        await seed_factor_commons(session, "consumable_accessories")
        await seed_factor_commons(session, "biological_chemical_gaseous_product")
        await seed_factor_commons(session, "services")
        await seed_factor_commons(session, "vehicles")
        await seed_factor_commons(session, "other_purchases")
        await seed_factor_additional(session)

        carbon_report_module_id_12345 = await get_carbon_report_module_id(
            unit_provider_code="12345",
            year=2025,
            module_type_id=ModuleTypeEnum.purchase,
        )
        await seed_data_commons(
            session, "scientific_equipment", carbon_report_module_id_12345
        )
        await seed_data_commons(session, "it_equipment", carbon_report_module_id_12345)
        await seed_data_commons(
            session, "consumable_accessories", carbon_report_module_id_12345
        )
        await seed_data_commons(
            session,
            "biological_chemical_gaseous_product",
            carbon_report_module_id_12345,
        )
        await seed_data_commons(session, "services", carbon_report_module_id_12345)
        await seed_data_commons(session, "vehicles", carbon_report_module_id_12345)
        await seed_data_commons(
            session, "other_purchases", carbon_report_module_id_12345
        )
        await seed_data_additional(session, carbon_report_module_id_12345)

    logger.info("Purchase data seeding completed.")


if __name__ == "__main__":
    asyncio.run(main())
