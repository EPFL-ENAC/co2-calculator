"""Main seed script to orchestrate all seeding operations in the correct order."""

import asyncio
import sys
import traceback

from app.seed.random_generator.populate_units_and_users import (
    main as seed_units_users,
)
from app.seed.random_generator.seed_carbon_reports import main as seed_carbon_reports
from app.seed.random_generator.seed_data_entries import main as seed_data_entries
from app.seed.random_generator.seed_factors import main as seed_factors
from app.seed.random_generator.seed_post_all import main as seed_post_all


async def main():
    """Run all seeding operations in the correct order."""
    print("Starting comprehensive data seeding...")

    try:
        print("\n1. Seeding units and users...")
        await seed_units_users()
        print("✓ Units and users seeded successfully")

        print("\n2. Seeding carbon reports and modules...")
        await seed_carbon_reports()
        print("✓ Carbon reports and modules seeded successfully")

        print("\n3. Seeding factors...")
        await seed_factors()
        print("✓ Factors seeded successfully")

        print("\n4. Seeding data entries and emissions...")
        await seed_data_entries()
        print("✓ Data entries and emissions seeded successfully")

        print("\n5. Re-creating indexes / FKs on data tables...")
        await seed_post_all()
        print("\nAll seeding operations completed successfully!")

    except Exception as e:
        print(f"\n❌ Seeding failed with error: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
