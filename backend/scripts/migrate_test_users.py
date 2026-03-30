#!/usr/bin/env python3
"""Migration script to fix test users with non-TEST- institutional_ids.

This script updates existing test user records to use the proper TEST- prefix
in their institutional_id field, preventing collisions with real user IDs.

IMPORTANT: Run this script BEFORE deploying the authentication hardening changes.
"""

import asyncio

from dotenv import load_dotenv
from sqlalchemy import text

from app.db import engine
from app.models.user import UserProvider
from app.providers.test_fixtures import (
    TEST_USERS,
)

load_dotenv()


async def migrate_test_users():
    """Migrate test users to use TEST- prefixed institutional_ids."""
    async with engine.connect() as conn:
        # First, find all affected test users
        query = text("""
            SELECT id, email, institutional_id, provider
            FROM users
            WHERE provider = :provider
              AND institutional_id NOT LIKE 'TEST-%'
            ORDER BY id
        """)

        result = await conn.execute(query, {"provider": UserProvider.TEST.name})
        rows = result.fetchall()

        if not rows:
            print("✓ No test users need migration.")
            return True

        print(f"Found {len(rows)} test user(s) to migrate:")
        print("-" * 80)
        for row in rows:
            print(
                f"  ID: {row.id}, Email: {row.email},"
                f" Current ID: {row.institutional_id}"
            )
        print("-" * 80)
        print()

        # Migrate each user
        migrated_count = 0
        for row in rows:
            # Determine the correct institutional_id based on email
            # Match email to TEST_USERS to get the proper TEST- prefixed ID
            correct_institutional_id = None
            for role_name, user_data in TEST_USERS.items():
                if user_data["email"] == row.email:
                    correct_institutional_id = user_data["institutional_id"]
                    break

            if not correct_institutional_id:
                print(f"⚠️  WARNING: No matching TEST_USER entry for email: {row.email}")
                print(f"   Skipping migration for user ID: {row.id}")
                continue

            # Update the institutional_id
            update_query = text("""
                UPDATE users
                SET institutional_id = :new_id
                WHERE id = :user_id
            """)

            await conn.execute(
                update_query, {"new_id": correct_institutional_id, "user_id": row.id}
            )

            print(
                f"✓ Migrated user {row.id}:"
                f" {row.institutional_id} -> {correct_institutional_id}"
            )
            migrated_count += 1

        # Commit the transaction
        await conn.commit()

        print()
        print(f"Migration complete! {migrated_count} user(s) updated.")
        print("✓ Test users now have proper TEST- prefixed institutional_ids.")
        return True


if __name__ == "__main__":
    try:
        result = asyncio.run(migrate_test_users())
        exit(0 if result else 1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
