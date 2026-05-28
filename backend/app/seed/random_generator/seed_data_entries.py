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
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES
from app.modules import (
    BuildingRoomHandlerCreate,
    EnergyCombustionHandlerCreate,
    EquipmentHandlerCreate,
    ExternalAIHandlerCreate,
    ExternalCloudHandlerCreate,
    HeadCountCreate,
    HeadCountStudentCreate,
    ProcessEmissionsHandlerCreate,
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelTrainHandlerCreate,
    PurchaseAdditionalHandlerCreate,
    PurchaseHandlerCreate,
    ResearchFacilitiesAnimalHandlerCreate,
    ResearchFacilitiesCommonHandlerCreate,
)
from app.modules.buildings.schemas import (
    VALID_ROOM_TYPES,
    BuildingEmbodiedEnergyHandlerCreate,
)
from app.modules.external_cloud_and_ai.schemas import REQUESTS_FREQUENCY_OPTIONS
from app.modules.headcount.schemas import POSITION_CATEGORY_VALUES
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
    # Schema mirrors ``DataEntryEmissionBase`` — ``subcategory`` and
    # ``formula_version`` were dropped from the table; do not re-add them.
    await conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS tmp_emissions (
            data_entry_id INT,
            emission_type_id INT,
            primary_factor_id INT,
            kg_co2eq FLOAT,
            additional_value FLOAT,
            scope INT,
            meta JSONB,
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
            kg_co2eq,
            additional_value,
            scope,
            meta,
            computed_at
        )
        SELECT *
        FROM tmp_emissions
    """)


# ============================================================
# DATA GENERATION
# ============================================================

# Maps every DataEntryTypeEnum that the random generator may emit (per
# MODULE_TYPE_TO_DATA_ENTRY_TYPES) to the Pydantic create-DTO that owns its
# JSON payload contract. Keeping this exhaustive prevents the generator's
# random module-type pick from raising KeyError mid-batch.
DATA_ENTRY_TYPE_TO_DTO: dict[DataEntryTypeEnum, type] = {
    # headcount
    DataEntryTypeEnum.member: HeadCountCreate,
    DataEntryTypeEnum.student: HeadCountStudentCreate,
    # professional travel
    DataEntryTypeEnum.plane: ProfessionalTravelPlaneHandlerCreate,
    DataEntryTypeEnum.train: ProfessionalTravelTrainHandlerCreate,
    # equipment electric consumption
    DataEntryTypeEnum.scientific: EquipmentHandlerCreate,
    DataEntryTypeEnum.it: EquipmentHandlerCreate,
    DataEntryTypeEnum.other: EquipmentHandlerCreate,
    # buildings
    DataEntryTypeEnum.building: BuildingRoomHandlerCreate,
    DataEntryTypeEnum.energy_combustion: EnergyCombustionHandlerCreate,
    DataEntryTypeEnum.building_embodied_energy: BuildingEmbodiedEnergyHandlerCreate,
    # external cloud & AI
    DataEntryTypeEnum.external_clouds: ExternalCloudHandlerCreate,
    DataEntryTypeEnum.external_ai: ExternalAIHandlerCreate,
    # process emissions
    DataEntryTypeEnum.process_emissions: ProcessEmissionsHandlerCreate,
    # purchases (standard purchase DTO covers all subkinds except
    # ``additional_purchases``, which has its own DTO).
    DataEntryTypeEnum.scientific_equipment: PurchaseHandlerCreate,
    DataEntryTypeEnum.it_equipment: PurchaseHandlerCreate,
    DataEntryTypeEnum.consumable_accessories: PurchaseHandlerCreate,
    DataEntryTypeEnum.biological_chemical_gaseous_product: PurchaseHandlerCreate,
    DataEntryTypeEnum.services: PurchaseHandlerCreate,
    DataEntryTypeEnum.vehicles: PurchaseHandlerCreate,
    DataEntryTypeEnum.other_purchases: PurchaseHandlerCreate,
    DataEntryTypeEnum.additional_purchases: PurchaseAdditionalHandlerCreate,
    # research facilities
    DataEntryTypeEnum.research_facilities: ResearchFacilitiesCommonHandlerCreate,
    DataEntryTypeEnum.mice_and_fish_animal_facilities: (
        ResearchFacilitiesAnimalHandlerCreate
    ),
}


def maybe(value, probability=0.5):  # nosec B311
    return value if random.random() < probability else None  # nosec B311


def _user_institutional_id() -> str:
    # populate_units_and_users emits ``USR000000``-style ids; mirror that shape
    # so future joins (where applicable) line up. Random suffix is fine — these
    # payloads are decoupled from the users table at the DB level.
    return f"USR{random.randint(0, 999999):06d}"  # nosec B311


def build_plane_travel() -> dict:
    return {
        "user_institutional_id": _user_institutional_id(),
        "origin_iata": fake.lexify(text="???").upper(),
        "destination_iata": fake.lexify(text="???").upper(),
        "cabin_class": random.choice(["eco", "business", "first"]),  # nosec B311
        "departure_date": date.today().isoformat(),
        "number_of_trips": random.randint(1, 10),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_train_travel() -> dict:
    return {
        "user_institutional_id": _user_institutional_id(),
        "origin_name": fake.city(),
        "destination_name": fake.city(),
        "cabin_class": random.choice(["first", "second"]),  # nosec B311
        "departure_date": date.today().isoformat(),
        "number_of_trips": random.randint(1, 10),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_equipment() -> dict:
    # ``equipment_class`` is required (``str``, not Optional) on the create DTO.
    # ``active`` + ``standby`` hours must sum to ≤ 168 per the mixin validator.
    active = random.randint(0, 80)  # nosec B311
    standby = random.randint(0, 168 - active)  # nosec B311
    return {
        "name": fake.word(),
        "equipment_class": fake.word(),
        "sub_class": maybe(fake.word()),
        "active_usage_hours_per_week": active,
        "standby_usage_hours_per_week": standby,
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_external_cloud() -> dict:
    return {
        "service_type": fake.word(),
        "provider": random.choice(["AWS", "Azure", "GCP"]),  # nosec B311
        "spent_amount": round(random.uniform(0, 5000), 2),  # nosec B311
        "currency": random.choice(["chf", "eur", "usd"]),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_external_ai() -> dict:
    return {
        "provider": random.choice(["OpenAI", "Anthropic", "Mistral"]),  # nosec B311
        "usage_type": fake.sentence(nb_words=3),
        "requests_per_user_per_day": maybe(
            random.choice(REQUESTS_FREQUENCY_OPTIONS),  # nosec B311
        ),
        # fte_count must be ≥ 0.1 per the schema validator.
        "fte_count": round(random.uniform(0.1, 500.0), 2),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_headcount() -> dict:
    return {
        "name": fake.name(),
        "position_title": maybe(fake.job()),
        "position_category": maybe(
            random.choice(sorted(POSITION_CATEGORY_VALUES)),  # nosec B311
        ),
        "fte": maybe(round(random.uniform(0.1, 1.0), 2)),  # nosec B311
        # user_institutional_id is required (non-Optional) on the create DTO.
        "user_institutional_id": _user_institutional_id(),
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_student() -> dict:
    return {
        "fte": round(random.uniform(0.1, 1.0), 2),  # nosec B311
    }


def build_purchase() -> dict:
    return {
        "name": fake.word(),
        "supplier": maybe(fake.company()),
        "quantity": maybe(round(random.uniform(1, 100), 2)),  # nosec B311
        # total_spent_amount is required (non-Optional) on the create DTO.
        "total_spent_amount": round(random.uniform(100, 10000), 2),  # nosec B311
        "currency": random.choice(["chf", "eur", "usd"]),  # nosec B311
        "purchase_institutional_code": maybe(fake.bothify(text="???-#####")),  # nosec B311
        "purchase_additional_code": maybe(fake.bothify(text="???-#####")),  # nosec B311
        "note": maybe(fake.sentence(nb_words=10)),
    }


def build_purchase_additional() -> dict:
    return {
        "name": fake.word(),
        "unit": random.choice(["kg", "liter", "piece"]),  # nosec B311
        "annual_consumption": round(random.uniform(0, 5000), 2),  # nosec B311
        "coef_to_kg": round(random.uniform(0.01, 10.0), 3),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_building_room() -> dict:
    return {
        "building_name": fake.last_name() + " Hall",
        "room_name": f"R{random.randint(100, 999)}",  # nosec B311
        "room_type": random.choice(  # nosec B311
            [t for t in VALID_ROOM_TYPES if t is not None]
        ),
        "room_allocation_ratio": round(random.uniform(0.0, 1.0), 2),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_energy_combustion() -> dict:
    return {
        "name": fake.word(),
        "quantity": round(random.uniform(0, 5000), 2),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_building_embodied_energy() -> dict:
    return {
        "building_name": fake.last_name() + " Hall",
    }


def build_process_emissions() -> dict:
    return {
        "category": fake.word(),
        "subcategory": maybe(fake.word()),
        "quantity": round(random.uniform(0, 5000), 2),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_research_facility_common() -> dict:
    return {
        "researchfacility_id": maybe(fake.bothify(text="RF-#####")),
        "researchfacility_name": maybe(fake.company()),
        "use": maybe(round(random.uniform(0, 1000), 2)),  # nosec B311
        "use_unit": maybe(random.choice(["kg", "liter", "hour"])),  # nosec B311
        "note": maybe(fake.sentence(nb_words=6)),
    }


def build_research_facility_animal() -> dict:
    payload = build_research_facility_common()
    payload["researchfacility_type"] = maybe(
        random.choice(["mice", "fish", "rat"]),  # nosec B311
    )
    return payload


DTO_BUILDERS: dict[type, object] = {
    ProfessionalTravelPlaneHandlerCreate: build_plane_travel,
    ProfessionalTravelTrainHandlerCreate: build_train_travel,
    EquipmentHandlerCreate: build_equipment,
    ExternalCloudHandlerCreate: build_external_cloud,
    ExternalAIHandlerCreate: build_external_ai,
    HeadCountCreate: build_headcount,
    HeadCountStudentCreate: build_student,
    PurchaseHandlerCreate: build_purchase,
    PurchaseAdditionalHandlerCreate: build_purchase_additional,
    BuildingRoomHandlerCreate: build_building_room,
    EnergyCombustionHandlerCreate: build_energy_combustion,
    BuildingEmbodiedEnergyHandlerCreate: build_building_embodied_energy,
    ProcessEmissionsHandlerCreate: build_process_emissions,
    ResearchFacilitiesCommonHandlerCreate: build_research_facility_common,
    ResearchFacilitiesAnimalHandlerCreate: build_research_facility_animal,
}


# Tuned to land at ~800 data_entry rows total:
# NUM_UNITS (5) × YEARS (3) × ALL_MODULE_TYPE_IDS (8) × avg ~7 = 840.
# See docs/src/implementation-plans/222-seed-data-faker.md for the math.
ENTRIES_PER_MODULE_MIN = 4
ENTRIES_PER_MODULE_MAX = 10


def generate_data_entries_for_module(module_id, module_type_id):
    rows = []
    now_status_values = [s.value for s in DataEntryStatusEnum]

    num_entries = random.randint(  # nosec B311
        ENTRIES_PER_MODULE_MIN, ENTRIES_PER_MODULE_MAX
    )

    matching_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(
        module_type_id, [DataEntryTypeEnum.member]
    )

    for _ in range(num_entries):
        data_entry_type = random.choice(matching_types)  # nosec B311

        dto_class = DATA_ENTRY_TYPE_TO_DTO[data_entry_type]
        builder = DTO_BUILDERS[dto_class]

        payload_dict = builder()

        # Validate against the real Pydantic DTO so payload drift surfaces here
        # rather than at first read by the app. ``DataEntryPayloadMixin`` wraps
        # the flat dict into ``{"data": {...}}``; we persist the inner dict so
        # the JSONB column stays flat (matches what the API would store).
        dto_instance = dto_class(
            data_entry_type_id=data_entry_type.value,
            carbon_report_module_id=module_id,
            **payload_dict,
        )

        rows.append(
            (
                data_entry_type.value,
                module_id,
                json.dumps(dto_instance.data, default=str),
                random.choice(now_status_values),  # nosec B311
            )
        )

    return rows


def generate_emissions_for_entry(entry_id, data_entry_type_id):
    rows = []
    now = datetime.now(timezone.utc)

    # simple placeholder logic for speed — no factor lookup; primary_factor_id
    # stays NULL. Fields mirror ``DataEntryEmissionBase``.
    emission_type = random.choice(list(EmissionType))  # nosec B311
    scope = emission_type.scope.value if emission_type.scope is not None else None

    rows.append(
        (
            entry_id,
            emission_type.value,
            None,  # primary_factor_id
            round(random.uniform(10, 500), 4),  # kg_co2eq  # nosec B311
            None,  # additional_value
            scope,
            json.dumps({"seeded": True, "formula_version": versionapi}),
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
