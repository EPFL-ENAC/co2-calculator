"""Main seed script to orchestrate all seeding operations in the correct order."""

import asyncio
import os
import sys
import traceback
from urllib.parse import urlsplit

from app.core.config import get_settings
from app.seed.random_generator.populate_units_and_users import (
    main as seed_units_users,
)
from app.seed.random_generator.seed_carbon_reports import YEARS
from app.seed.random_generator.seed_carbon_reports import main as seed_carbon_reports
from app.seed.random_generator.seed_data_entries import main as seed_data_entries
from app.seed.random_generator.seed_post_all import main as seed_post_all
from app.seed.random_generator.seed_year_configuration import (
    main as seed_year_configuration,
)

# Canonical CSV-based factor seeder; replaces random_generator.seed_factors,
# which drifted from the current factor schema and produced duplicate
# (data_entry_type_id, emission_type_id, classification) rows.
from app.seed.seed_generic_factors import main as seed_factors


def _guard_target_db() -> None:
    """Refuse to bulk-seed a non-local database unless explicitly allowed.

    backend/.env commonly points DB_URL at the shared dev platform; dumping
    millions of fake rows there by accident is unrecoverable. Inline env
    vars don't reliably override dotenv here, so check the effective URL.
    """
    settings = get_settings()
    if settings.DB_URL is None:
        raise SystemExit("DB_URL must be set to run this seed script")
    host = urlsplit(
        settings.DB_URL.replace("postgresql+psycopg", "postgresql")
    ).hostname
    print(f"Target database host: {host}")
    if host in ("localhost", "127.0.0.1"):
        return
    if os.environ.get("SEED_ALLOW_REMOTE") == "1":
        return
    raise SystemExit(
        f"Refusing to bulk-seed non-local database host {host!r}. "
        "Set SEED_ALLOW_REMOTE=1 if this is intentional."
    )


async def main():
    """Run all seeding operations in the correct order."""
    _guard_target_db()
    print("Starting comprehensive data seeding...")

    try:
        print("\n1. Seeding units and users...")
        await seed_units_users()
        print("✓ Units and users seeded successfully")

        print("\n2. Seeding year configurations...")
        await seed_year_configuration()
        print("✓ Year configurations seeded successfully")

        print("\n3. Seeding carbon reports and modules...")
        await seed_carbon_reports()
        print("✓ Carbon reports and modules seeded successfully")

        print("\n4. Seeding factors...")
        # Every seeded year needs its factor set: year-scoped modules
        # (energy_combustion, external_clouds, ...) hard-fail ingest and
        # recalc for a year with no factors.
        await seed_factors(years=YEARS)
        print("✓ Factors seeded successfully")

        print("\n5. Seeding data entries and emissions...")
        await seed_data_entries()
        print("✓ Data entries and emissions seeded successfully")

        print("\n6. Re-creating indexes / FKs on data tables...")
        await seed_post_all()
        print("\nAll seeding operations completed successfully!")

    except Exception as e:
        print(f"\n❌ Seeding failed with error: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
