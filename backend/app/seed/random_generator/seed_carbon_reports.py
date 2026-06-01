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
from app.core.constants import ModuleStatus
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
# CARBON PROJECTS
# ============================================================


async def insert_carbon_projects(conn):
    """Create one Calculator project per unit.

    `carbon_reports.UNIQUE(carbon_project_id, year)` requires a non-null
    `carbon_project_id` for the dedup path to work, and the UI hangs all
    reports off a project, so every seeded unit gets a Calculator project.
    """
    units = await conn.fetch("SELECT id FROM units")
    unit_ids = [u["id"] for u in units]

    print(f"Creating Calculator projects for {len(unit_ids)} units...")

    start_year = min(YEARS)
    end_year = max(YEARS)
    records = [(u_id, "Calculator", start_year, end_year, False) for u_id in unit_ids]

    await conn.execute("""
        CREATE TEMP TABLE tmp_carbon_projects (
            unit_id INTEGER,
            carbon_report_type TEXT,
            start_year INTEGER,
            end_year INTEGER,
            is_viewable_by_unit_members BOOLEAN
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table("tmp_carbon_projects", records=records)

    await conn.execute("""
        INSERT INTO carbon_projects (
            unit_id,
            carbon_report_type,
            start_year,
            end_year,
            is_viewable_by_unit_members
        )
        SELECT
            unit_id,
            carbon_report_type::carbon_report_type_enum,
            start_year,
            end_year,
            is_viewable_by_unit_members
        FROM tmp_carbon_projects
        ON CONFLICT (unit_id, carbon_report_type) DO NOTHING
    """)

    rows = await conn.fetch(
        "SELECT id, unit_id FROM carbon_projects "
        "WHERE carbon_report_type = 'Calculator'"
    )
    return {r["unit_id"]: r["id"] for r in rows}


# ============================================================
# CARBON REPORTS
# ============================================================


async def insert_carbon_reports(conn, unit_to_project):
    print(f"Creating carbon reports for {len(unit_to_project)} units...")

    records = [
        (year, unit_id, project_id)
        for unit_id, project_id in unit_to_project.items()
        for year in YEARS
    ]

    await conn.execute("""
        CREATE TEMP TABLE tmp_carbon_reports (
            year INTEGER,
            unit_id INTEGER,
            carbon_project_id INTEGER
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table("tmp_carbon_reports", records=records)

    inserted = await conn.fetch("""
        INSERT INTO carbon_reports (year, unit_id, carbon_project_id)
        SELECT year, unit_id, carbon_project_id
        FROM tmp_carbon_reports
        ON CONFLICT (carbon_project_id, year) DO NOTHING
        RETURNING id
    """)

    print(f"✓ Inserted {len(inserted)} carbon reports")

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
                    random.choice(statuses),  # nosec B311
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
            print("\nSeeding carbon projects, reports and modules...\n")

            unit_to_project = await insert_carbon_projects(conn)
            report_ids = await insert_carbon_reports(conn, unit_to_project)
            await insert_carbon_report_modules(conn, report_ids)

        print("\nAll carbon projects, reports and modules seeded successfully!\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
