"""
Ultra-fast PostgreSQL COPY seeder for:

- data_entries
- data_entry_emissions

Pure asyncpg.
Single transaction.
No ORM inserts.
"""

import asyncio
import json
import random
from datetime import date, datetime, timezone

import asyncpg
from faker import Faker

from app.core.config import get_settings
from app.models.data_entry import DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.models.location import TransportModeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES
from app.modules import (
    EquipmentHandlerCreate,
    ExternalAIHandlerCreate,
    ExternalCloudHandlerCreate,
    HeadCountCreate,
    HeadCountStudentCreate,
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelTrainHandlerCreate,
)
from app.modules.purchase.schemas import PurchaseHandlerCreate
from app.seed.seed_helper import versionapi

fake = Faker()
BATCH_SIZE = 1000


# ============================================================
# DB CONNECTION
# ============================================================


async def get_connection():
    settings = get_settings()
    db_url = settings.DB_URL.replace("postgresql+psycopg", "postgresql")
    return await asyncpg.connect(db_url)


# ============================================================
# COPY HELPERS
# ============================================================


async def copy_insert_data_entries(conn, rows):
    await conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS tmp_data_entries (
            data_entry_type_id INT,
            carbon_report_module_id INT,
            data JSONB,
            status INT
        ) ON COMMIT DROP
    """)

    await conn.execute("TRUNCATE tmp_data_entries")

    await conn.copy_records_to_table(
        "tmp_data_entries",
        records=rows,
    )

    inserted = await conn.fetch("""
        INSERT INTO data_entries (
            data_entry_type_id,
            carbon_report_module_id,
            data,
            status,
            created_at,
            updated_at
        )
        SELECT
            data_entry_type_id,
            carbon_report_module_id,
            data,
            CASE status
                WHEN 0 THEN 'PENDING'::dataentrystatusenum
                WHEN 1 THEN 'VALIDATED'::dataentrystatusenum
                WHEN 2 THEN 'REJECTED'::dataentrystatusenum
                ELSE 'PENDING'::dataentrystatusenum
            END,
            NOW(),
            NOW()
        FROM tmp_data_entries
        RETURNING id
    """)

    return [r["id"] for r in inserted]


async def copy_insert_emissions(conn, rows):
    await conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS tmp_emissions (
            data_entry_id INT,
            emission_type_id INT,
            primary_factor_id INT,
            subcategory TEXT,
            kg_co2eq FLOAT,
            meta JSONB,
            formula_version TEXT,
            computed_at TIMESTAMPTZ
        ) ON COMMIT DROP
    """)

    await conn.execute("TRUNCATE tmp_emissions")

    await conn.copy_records_to_table(
        "tmp_emissions",
        records=rows,
    )

    await conn.execute("""
        INSERT INTO data_entry_emissions (
            data_entry_id,
            emission_type_id,
            primary_factor_id,
            subcategory,
            kg_co2eq,
            meta,
            formula_version,
            computed_at
        )
        SELECT *
        FROM tmp_emissions
    """)


# ============================================================
# DATA GENERATION
# ============================================================

DATA_ENTRY_TYPE_TO_DTO = {
    DataEntryTypeEnum.plane: ProfessionalTravelPlaneHandlerCreate,
    DataEntryTypeEnum.train: ProfessionalTravelTrainHandlerCreate,
    DataEntryTypeEnum.it: EquipmentHandlerCreate,
    DataEntryTypeEnum.scientific: EquipmentHandlerCreate,
    DataEntryTypeEnum.other: EquipmentHandlerCreate,
    DataEntryTypeEnum.external_clouds: ExternalCloudHandlerCreate,
    DataEntryTypeEnum.external_ai: ExternalAIHandlerCreate,
    DataEntryTypeEnum.member: HeadCountCreate,
    DataEntryTypeEnum.student: HeadCountStudentCreate,
    DataEntryTypeEnum.building: EquipmentHandlerCreate,
    DataEntryTypeEnum.process_emissions: EquipmentHandlerCreate,
    DataEntryTypeEnum.energy_mix: EquipmentHandlerCreate,
    DataEntryTypeEnum.it_equipment: PurchaseHandlerCreate,
    DataEntryTypeEnum.other_purchases: PurchaseHandlerCreate,
    DataEntryTypeEnum.scientific_equipment: EquipmentHandlerCreate,
    DataEntryTypeEnum.it_equipment: PurchaseHandlerCreate,
    DataEntryTypeEnum.consumable_accessories: PurchaseHandlerCreate,
    DataEntryTypeEnum.biological_chemical_gaseous_product: PurchaseHandlerCreate,
    DataEntryTypeEnum.services: PurchaseHandlerCreate,
    DataEntryTypeEnum.vehicles: PurchaseHandlerCreate,
    DataEntryTypeEnum.other_purchases: PurchaseHandlerCreate,
    DataEntryTypeEnum.additional_purchases: PurchaseHandlerCreate,
}


def maybe(value, probability=0.5):  # nosec B311
    return value if random.random() < probability else None  # nosec B311


def build_professional_travel():
    return {
        "traveler_name": fake.name(),
        "traveler_id": maybe(random.randint(1, 1000)),  # nosec B311
        "origin_location_id": random.randint(1, 200),  # nosec B311
        "destination_location_id": random.randint(1, 200),  # nosec B311
        "transport_mode": random.choice(list(TransportModeEnum)).value,  # nosec B311
        "cabin_class": maybe(random.choice(["eco", "business", "first"])),  # nosec B311
        "departure_date": maybe(date.today()),
        "number_of_trips": random.randint(1, 10),  # nosec B311
        "is_round_trip": random.choice([True, False]),  # nosec B311
        "trip_direction": maybe(random.choice(["outbound", "return"])),  # nosec B311
    }


def build_equipment():
    return {
        "name": fake.word(),
        "equipment_class": maybe(fake.word()),
        "sub_class": maybe(fake.word()),
        "active_usage_hours": maybe(random.randint(0, 168)),  # nosec B311
        "passive_usage_hours": maybe(random.randint(0, 168)),  # nosec B311
    }


def build_external_cloud():
    return {
        "service_type": fake.word(),
        "cloud_provider": maybe(random.choice(["AWS", "Azure", "GCP"])),  # nosec B311
        "spending": round(random.uniform(0, 5000), 2),  # nosec B311
    }


def build_external_ai():
    return {
        "ai_provider": random.choice(["OpenAI", "Anthropic", "Mistral"]),  # nosec B311
        "ai_use": fake.sentence(nb_words=3),
        "frequency_use_per_day": maybe(random.randint(0, 50)),  # nosec B311
        "user_count": random.randint(1, 500),  # nosec B311
    }


def build_headcount():
    return {
        "name": fake.name(),
        "function": maybe(fake.job()),
        "fte": maybe(round(random.uniform(0.1, 1.0), 2)),  # nosec B311
        "sciper": maybe(str(random.randint(100000, 999999))),  # nosec B311
    }


def build_student():
    return {
        "fte": round(random.uniform(0.1, 1.0), 2),  # nosec B311
    }


def build_purchase():
    return {
        "name": fake.word(),
        "supplier": maybe(fake.company()),
        "quantity": maybe(random.randint(1, 100)),  # nosec B311
        "total_spent_amount": maybe(round(random.uniform(100, 10000), 2)),  # nosec B311
        "purchase_institutional_code": maybe(fake.bothify(text="???-#####")),  # nosec B311
        "purchase_institutional_description": maybe(fake.sentence(nb_words=5)),
        "purchase_additional_code": maybe(fake.bothify(text="???-#####")),  # nosec B311
        "note": maybe(fake.sentence(nb_words=10)),
    }


DTO_BUILDERS = {
    ProfessionalTravelPlaneHandlerCreate: build_professional_travel,
    ProfessionalTravelTrainHandlerCreate: build_professional_travel,
    EquipmentHandlerCreate: build_equipment,
    ExternalCloudHandlerCreate: build_external_cloud,
    ExternalAIHandlerCreate: build_external_ai,
    HeadCountCreate: build_headcount,
    HeadCountStudentCreate: build_student,
    PurchaseHandlerCreate: build_purchase,
}


def generate_data_entries_for_module(module_id, module_type_id):
    rows = []
    now_status_values = [s.value for s in DataEntryStatusEnum]

    num_entries = random.randint(10, 220)  # nosec B311

    matching_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(
        module_type_id, [DataEntryTypeEnum.member]
    )

    for _ in range(num_entries):
        data_entry_type = random.choice(matching_types)  # nosec B311

        dto_class = DATA_ENTRY_TYPE_TO_DTO[data_entry_type]
        builder = DTO_BUILDERS[dto_class]

        payload_dict = builder()

        # Validate against real DTO
        # dto_instance = dto_class(**payload_dict)

        rows.append(
            (
                data_entry_type.value,
                module_id,
                # dto_instance.model_dump_json(),
                json.dumps(payload_dict, default=str),
                random.choice(now_status_values),  # nosec B311
            )
        )

    return rows


def generate_emissions_for_entry(entry_id, data_entry_type_id):
    rows = []
    now = datetime.now(timezone.utc)

    # simple placeholder logic for speed  # nosec B311
    emission_type = random.choice(list(EmissionType))  # nosec B311

    rows.append(
        (
            entry_id,
            emission_type.value,
            None,
            emission_type.name,
            round(random.uniform(10, 500), 4),  # nosec B311
            json.dumps({"seeded": True}),
            versionapi,
            now,
        )
    )

    return rows


# ============================================================
# MAIN SEEDER
# ============================================================


async def main():
    conn = await get_connection()

    COMMIT_EVERY = 10
    transaction = None

    try:
        print("Fetching carbon report modules...")
        modules = await conn.fetch(
            "SELECT id, module_type_id FROM carbon_report_modules"
        )

        print(f"Seeding data for {len(modules)} modules...\n")

        total_entries = 0
        total_emissions = 0
        batch_number = 0

        for i in range(0, len(modules), BATCH_SIZE):
            batch_number += 1

            # Start new transaction block every COMMIT_EVERY batches
            if (batch_number - 1) % COMMIT_EVERY == 0:
                transaction = conn.transaction()
                await transaction.start()

            batch = modules[i : i + BATCH_SIZE]

            data_entry_rows = []

            for module in batch:
                data_entry_rows.extend(
                    generate_data_entries_for_module(
                        module["id"],
                        module["module_type_id"],
                    )
                )

            if not data_entry_rows:
                continue

            returned_ids = await copy_insert_data_entries(
                conn,
                data_entry_rows,
            )

            emission_rows = []

            for idx, entry_id in enumerate(returned_ids):
                data_entry_type_id = data_entry_rows[idx][0]
                emission_rows.extend(
                    generate_emissions_for_entry(
                        entry_id,
                        data_entry_type_id,
                    )
                )

            if emission_rows:
                await copy_insert_emissions(conn, emission_rows)

            total_entries += len(returned_ids)
            total_emissions += len(emission_rows)

            print(
                f"Batch {batch_number} | "
                f"{len(returned_ids)} entries | "
                f"{len(emission_rows)} emissions"
            )

            # Commit every COMMIT_EVERY batches
            if batch_number % COMMIT_EVERY == 0:
                await transaction.commit()
                print(f"✓ Committed up to batch {batch_number}\n")
                transaction = None

        # Commit remaining batches if not multiple of COMMIT_EVERY
        if transaction is not None:
            await transaction.commit()
            print("✓ Final commit completed\n")

        print("✓ Seeding completed")
        print(f"TOTAL: {total_entries} data entries")
        print(f"TOTAL: {total_emissions} emissions")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
