"""
Ultra-fast PostgreSQL COPY seeder for:

- carbon_reports
- carbon_report_modules

Requirements:
- UNIQUE(year, unit_id)
- UNIQUE(carbon_report_id, module_type_id)

Pure asyncpg.
Idempotent.
"""

import asyncio
import random

import asyncpg

from app.core.config import get_settings
from app.models.carbon_report import ModuleStatus
from app.models.module_type import ALL_MODULE_TYPE_IDS

YEARS = [2023, 2024, 2025]


# ============================================================
# DATABASE
# ============================================================


async def get_connection():
    settings = get_settings()
    db_url = settings.DB_URL.replace("postgresql+psycopg", "postgresql")
    return await asyncpg.connect(db_url)


# ============================================================
# CARBON REPORTS
# ============================================================


async def insert_carbon_reports(conn):
    print("Fetching units...")

    units = await conn.fetch("SELECT id FROM units")
    unit_ids = [u["id"] for u in units]

    print(f"Creating carbon reports for {len(unit_ids)} units...")

    # Prepare records
    records = [(year, unit_id) for unit_id in unit_ids for year in YEARS]

    await conn.execute("""
        CREATE TEMP TABLE tmp_carbon_reports (
            year INTEGER,
            unit_id INTEGER
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table(
        "tmp_carbon_reports",
        records=records,
    )

    inserted = await conn.fetch("""
        INSERT INTO carbon_reports (year, unit_id)
        SELECT year, unit_id
        FROM tmp_carbon_reports
        ON CONFLICT (year, unit_id) DO NOTHING
        RETURNING id
    """)

    print(f"✓ Inserted {len(inserted)} carbon reports")

    # Fetch ALL report ids (including pre-existing ones)
    reports = await conn.fetch("SELECT id FROM carbon_reports")
    return [r["id"] for r in reports]


# ============================================================
# CARBON REPORT MODULES
# ============================================================


async def insert_carbon_report_modules(conn, report_ids):
    print(f"Creating carbon report modules for {len(report_ids)} reports...")

    module_type_ids = [m.value for m in ALL_MODULE_TYPE_IDS]
    statuses = [s.value for s in ModuleStatus]

    records = []

    for report_id in report_ids:
        for module_type_id in module_type_ids:
            records.append(
                (
                    module_type_id,
                    random.choice(statuses),
                    report_id,
                )
            )

    await conn.execute("""
        CREATE TEMP TABLE tmp_carbon_report_modules (
            module_type_id INTEGER,
            status INTEGER,
            carbon_report_id INTEGER
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table(
        "tmp_carbon_report_modules",
        records=records,
    )

    await conn.execute("""
        INSERT INTO carbon_report_modules (
            module_type_id,
            status,
            carbon_report_id
        )
        SELECT
            module_type_id,
            status,
            carbon_report_id
        FROM tmp_carbon_report_modules
        ON CONFLICT (carbon_report_id, module_type_id) DO NOTHING
    """)

    print("✓ Carbon report modules inserted")


# ============================================================
# MAIN
# ============================================================


async def main():
    conn = await get_connection()

    try:
        async with conn.transaction():
            print("\n2. Seeding carbon reports and modules...\n")

            report_ids = await insert_carbon_reports(conn)

            await insert_carbon_report_modules(conn, report_ids)

        print("\nAll carbon reports and modules seeded successfully!\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
