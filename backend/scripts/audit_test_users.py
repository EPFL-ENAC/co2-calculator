#!/usr/bin/env python3
"""Audit script to detect test users with non-TEST- prefixed institutional_ids."""

import asyncio

from dotenv import load_dotenv
from sqlalchemy import text

from app.db import engine
from app.models.user import UserProvider

load_dotenv()


async def audit_test_users():
    """Check for test users that may have collided with real institutional IDs."""
    async with engine.connect() as conn:
        # Query for TEST provider users without TEST- prefix
        query = text("""
            SELECT id, email, institutional_id, provider
            FROM users
            WHERE provider = :provider
              AND institutional_id NOT LIKE 'TEST-%'
            ORDER BY id
        """)

        result = await conn.execute(query, {"provider": UserProvider.TEST.name})
        rows = result.fetchall()

        if rows:
            print(
                f"⚠️  WARNING: Found {len(rows)} test user(s)"
                f" with non-TEST- institutional_id:"
            )
            print("-" * 80)
            for row in rows:
                print(
                    f"  ID: {row.id}, Email: {row.email},"
                    f" Institutional ID: {row.institutional_id}"
                )
            print("-" * 80)
            print(
                "\nThese records need manual review before"
                " deploying the authentication hardening."
            )
            return False
        else:
            print("✓ No test users with non-TEST- institutional_id found.")
            print("Database is clean for authentication hardening deployment.")
            return True


if __name__ == "__main__":
    result = asyncio.run(audit_test_users())
    exit(0 if result else 1)
