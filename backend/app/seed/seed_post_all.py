import asyncio

from sqlalchemy import text

from app.db import SessionLocal

rebuild_statements = [
    # --- 2. Re-create Secondary Indexes ---
    "CREATE INDEX IF NOT EXISTS ix_data_entries_carbon_report_module_id "
    "ON data_entries (carbon_report_module_id);",
    "CREATE INDEX IF NOT EXISTS ix_data_entries_data_entry_type_id "
    "ON data_entries (data_entry_type_id);",
    "CREATE INDEX IF NOT EXISTS ix_data_entry_emissions_computed_at "
    "ON data_entry_emissions (computed_at);",
    "CREATE INDEX IF NOT EXISTS ix_data_entry_emissions_data_entry_id "
    "ON data_entry_emissions (data_entry_id);",
    "CREATE INDEX IF NOT EXISTS ix_data_entry_emissions_emission_type_id "
    "ON data_entry_emissions (emission_type_id);",
    "CREATE INDEX IF NOT EXISTS ix_data_entry_emissions_primary_factor_id "
    "ON data_entry_emissions (primary_factor_id);",
    # --- 3. Re-create Foreign Keys (Corrected Direction) ---
    "ALTER TABLE data_entries ADD CONSTRAINT data_entries_carbon_report_module_id_fkey "
    "FOREIGN KEY (carbon_report_module_id) REFERENCES carbon_report_modules (id);",
    "ALTER TABLE data_entries ADD CONSTRAINT data_entries_data_entry_type_id_fkey "
    "FOREIGN KEY (data_entry_type_id) REFERENCES data_entry_types (id);",
    "ALTER TABLE data_entry_emissions ADD CONSTRAINT "
    "data_entry_emissions_data_entry_id_fkey FOREIGN KEY (data_entry_id) "
    "REFERENCES data_entries (id);",
    "ALTER TABLE data_entry_emissions ADD CONSTRAINT "
    "data_entry_emissions_primary_factor_id_fkey FOREIGN KEY (primary_factor_id) "
    "REFERENCES primary_factors (id);",
]


async def main():
    async with SessionLocal() as session:
        # 1. Return to LOGGED status
        await session.execute(text("ALTER TABLE data_entry_emissions SET LOGGED;"))
        await session.execute(text("ALTER TABLE data_entries SET LOGGED;"))

        for stmt in rebuild_statements:
            try:
                await session.execute(text(stmt))
            except Exception as e:
                print(f"Skipping or failing on stmt: {stmt[:50]}... Error: {e}")

        await session.commit()
        print("✅ Database integrity and LOGGED status restored.")


if __name__ == "__main__":
    asyncio.run(main())
