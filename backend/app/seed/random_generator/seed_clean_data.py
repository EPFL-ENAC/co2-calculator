import asyncio

from sqlalchemy import text
from sqlmodel import SQLModel

from app.db import SessionLocal, engine

statements = [
    # --- 1. Drop Foreign Keys on data_entries ---
    "ALTER TABLE data_entries DROP CONSTRAINT IF EXISTS "
    "data_entries_carbon_report_module_id_fkey;",
    "ALTER TABLE data_entries DROP CONSTRAINT IF EXISTS "
    "data_entries_data_entry_emission_id_fkey;",
    "ALTER TABLE data_entries DROP CONSTRAINT IF EXISTS "
    "data_entries_data_entry_type_id_fkey;",
    # --- 2. Drop Foreign Keys on data_entry_emissions ---
    "ALTER TABLE data_entry_emissions DROP CONSTRAINT IF EXISTS "
    "data_entry_emissions_data_entry_id_fkey;",
    "ALTER TABLE data_entry_emissions DROP CONSTRAINT IF EXISTS "
    "data_entry_emissions_primary_factor_id_fkey;",
    # --- 3. Drop Secondary Indexes (Keeping the PK index as requested) ---
    "DROP INDEX IF EXISTS ix_data_entries_carbon_report_module_id;",
    "DROP INDEX IF EXISTS ix_data_entries_data_entry_type_id;",
    "DROP INDEX IF EXISTS ix_data_entry_emissions_computed_at;",
    "DROP INDEX IF EXISTS ix_data_entry_emissions_data_entry_id;",
    "DROP INDEX IF EXISTS ix_data_entry_emissions_emission_type_id;",
    "DROP INDEX IF EXISTS ix_data_entry_emissions_primary_factor_id;",
    # --- 4. Switch to UNLOGGED (Now both are "disconnected" from logged tables) ---
    "ALTER TABLE data_entry_emissions SET UNLOGGED;",
    "ALTER TABLE data_entries SET UNLOGGED;",
]


async def main():
    async with SessionLocal() as session:
        # Clear existing data first (in correct order to handle foreign key constraints)
        # Clear existing data first (in correct order to handle foreign key constraints)
        await session.execute(text("DROP TABLE IF EXISTS tmp_data_entries"))
        await session.execute(text("DROP TABLE IF EXISTS data_entry_emissions"))
        await session.execute(text("DROP TABLE IF EXISTS data_entries"))
        await session.execute(text("DROP TABLE IF EXISTS carbon_report_modules"))
        await session.execute(text("DROP TABLE IF EXISTS carbon_reports"))
        await session.execute(text("DROP TABLE IF EXISTS unit_users"))
        await session.execute(text("DROP TABLE IF EXISTS units"))
        await session.execute(text("DROP TABLE IF EXISTS users"))
        await session.commit()

        # generate schema after dropping tables from
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        # 2. Drop constraints and indexes for speed
        # Note: We drop the emission fkey which was causing your specific error
        # 1. List of constraints and indexes to drop to allow
        # UNLOGGED and speed up seeding

        for stmt in statements:
            await session.execute(text(stmt))

        await session.execute(
            text(
                "ALTER TABLE carbon_reports ADD CONSTRAINT "
                "carbon_reports_year_unit_unique UNIQUE (year, unit_id);"
            )
        )

        await session.execute(
            text(
                "ALTER TABLE carbon_report_modules ADD CONSTRAINT "
                "carbon_report_modules_unique UNIQUE "
                "(carbon_report_id, module_type_id);"
            )
        )

        await session.commit()
        print("🚀 Constraints and indexes stripped. Tables set to UNLOGGED.")


if __name__ == "__main__":
    asyncio.run(main())
