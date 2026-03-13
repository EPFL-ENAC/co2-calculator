"""Main seed script to orchestrate all seeding operations in the correct order."""

import asyncio
import sys
import traceback

from app.db import SessionLocal
from app.models.user import UserProvider
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.repositories.unit_repo import UpsertResult
from app.repositories.user_repo import UpsertUserResult
from app.services.user_service import UserService

# The following SQL queries are useful for data integrity checks
# after seeding units from Accred API:

# -- Units with a principal that doesn't exist in users
# SELECT u.name, u.principal_user_institutional_id
# FROM units u
# LEFT JOIN users us ON u.principal_user_institutional_id = us.institutional_id
# WHERE u.principal_user_institutional_id IS NOT NULL
#   AND us.institutional_id IS NULL;

# -- Units with a parent_id that doesn't exist in units
# SELECT u.name, u.institutional_code, u.parent_institutional_code
# FROM units u
# LEFT JOIN units p ON u.parent_institutional_code = p.institutional_code
# WHERE u.parent_institutional_code IS NOT NULL
#   AND p.institutional_code IS NULL;


async def seed_units_accred() -> None:
    """create a unit provider and call
    fetch_all_units_from_accred to populate units from accred"""

    provider = get_unit_provider(UserProvider.ACCRED)
    role_provider = get_role_provider(UserProvider.ACCRED)
    units_raw, principal_users_raw = await provider.fetch_all_units()
    units = [provider.map_api_unit(unit) for unit in units_raw]
    principal_users = [role_provider.map_api_user(user) for user in principal_users_raw]
    print(f"Fetched {len(units)} units from Accred API, now bulk creating in DB...")
    async with SessionLocal() as session:
        from app.services.unit_service import UnitService

        unit_service = UnitService(session)
        results: UpsertResult = await unit_service.bulk_upsert(units)
        print(f"✓ Bulk upserted {len(units)} units from Accred API")
        print(f"Upsert results: {results}")
        await session.commit()
        print("✓ Committed units to database")
        # Optionally, also create principal users in the database if needed
        user_service = UserService(session)
        user_results: UpsertUserResult = await user_service.bulk_upsert(principal_users)
        print(f"✓ Bulk upserted {len(principal_users)} principal users from Accred API")
        print(f"User upsert results: {user_results}")
        await session.commit()
        print("✓ Committed principal users to database")


async def main():
    """Run all seeding operations in the correct order."""
    print("Starting comprehensive data seeding...")

    try:
        print("\n1. Seeding units and users...")
        await seed_units_accred()
        print("✓ Units and users seeded successfully")
    except Exception as e:
        print(f"\n❌ Seeding failed with error: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
