import asyncio

import asyncpg

from app.core.config import get_settings


async def check_enum_values():
    settings = get_settings()
    # Use the same DB_URL but with asyncpg driver
    db_url = settings.DB_URL.replace("postgresql+psycopg", "postgresql").replace(
        "postgresql://", "postgresql://"
    )

    conn = await asyncpg.connect(db_url)
    try:
        # Query to get enum values
        rows = await conn.fetch("""
            SELECT enumlabel 
            FROM pg_enum 
            WHERE enumtypid = 'role_name_enum'::regtype
            ORDER BY enumsortorder;
        """)

        print("Role name enum values in database:")
        for row in rows:
            print(f"  {row['enumlabel']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_enum_values())
