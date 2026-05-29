"""
Seed `year_configuration` rows so the seeded years are open for data entry.

Without this, `configuration_completed` is NULL on every (year, provider)
pair and the app blocks uploads / hides the year picker, which prevents
login-test users from reaching a perimeter scope.

Pure asyncpg. Idempotent via ON CONFLICT (year, provider).
"""

import asyncio
from datetime import datetime, timezone

import asyncpg

from app.core.config import get_settings
from app.models.user import UserProvider
from app.seed.random_generator.seed_carbon_reports import YEARS


async def get_connection():
    settings = get_settings()
    db_url = settings.DB_URL.replace("postgresql+psycopg", "postgresql")
    return await asyncpg.connect(db_url)


async def insert_year_configurations(conn):
    now_tz = datetime.now(timezone.utc)
    # `updated_at` is TIMESTAMP (no tz) per the SQLModel column default;
    # `configuration_completed` is TIMESTAMPTZ. Pass them as distinct
    # parameters so asyncpg can deduce each type unambiguously.
    now_naive = now_tz.replace(tzinfo=None)
    provider = UserProvider.DEFAULT.name

    for year in YEARS:
        await conn.execute(
            """
            INSERT INTO year_configuration (
                year,
                provider,
                is_started,
                configuration_completed,
                config,
                updated_at
            )
            VALUES (
                $1,
                $2::user_provider_enum,
                TRUE,
                $3::timestamptz,
                '{}'::jsonb,
                $4::timestamp
            )
            ON CONFLICT (year, provider) DO NOTHING
            """,
            year,
            provider,
            now_tz,
            now_naive,
        )

    print(f"✓ Year configurations ready for {YEARS} (provider={provider})")


async def main():
    conn = await get_connection()

    try:
        async with conn.transaction():
            print("\nSeeding year_configuration...\n")
            await insert_year_configurations(conn)
        print("\nYear configurations seeded successfully!\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
