"""Seed locations (train stations and airports) via PostgreSQL staging-table UPSERT.

Requires seed_travel_location_clean.csv to exist. Generate it once with:
    uv run -m app.seed.prepare_seed_locations
"""

import asyncio
from pathlib import Path

import psycopg
from sqlalchemy.engine.url import make_url

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CLEAN_CSV = (
    Path(__file__).parent.parent.parent / "seed_data" / "seed_travel_location_clean.csv"
)

_COPY_STAGING_SQL = (
    "COPY locations_staging ("
    "transport_mode, airport_size, name, latitude, longitude, "
    "continent, country_code, municipality, iata_code, keywords"
    ") FROM STDIN CSV HEADER NULL ''"
)

# Keep in lock-step with ``Location.compute_natural_key`` — the seed runs
# this in Postgres for bulk UPSERT while application code (ingestion, tests)
# calls the Python helper. Drift makes the same logical location dedupe to
# two different rows.
_NATURAL_KEY_EXPR = r"""
    CASE
        WHEN transport_mode = 'plane' AND iata_code IS NOT NULL
            THEN 'plane:' || iata_code
        WHEN transport_mode = 'train'
            THEN 'train:'
              || lower(coalesce(country_code, '')) || ':'
              || regexp_replace(lower(trim(name)), '\s+', ' ', 'g') || ':'
              || latitude || ':' || longitude
        ELSE
            'plane:'
              || lower(coalesce(country_code, '')) || ':'
              || regexp_replace(lower(trim(name)), '\s+', ' ', 'g') || ':'
              || latitude || ':' || longitude
    END
"""


async def seed_locations() -> None:
    if not CLEAN_CSV.exists():
        logger.error(f"Clean CSV not found: {CLEAN_CSV}")
        logger.error("Generate it first: uv run -m app.seed.prepare_seed_locations")
        return

    settings = get_settings()
    if not settings.DB_URL:
        logger.error("DB_URL not set")
        return
    url = make_url(settings.DB_URL)

    logger.info("Connecting to database...")
    async with await psycopg.AsyncConnection.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
    ) as conn:
        # 1. Create staging temp table (same columns as CSV, no id / natural_key)
        await conn.execute("""
            CREATE TEMP TABLE locations_staging (
                transport_mode TEXT, airport_size TEXT, name TEXT,
                latitude FLOAT, longitude FLOAT, continent TEXT,
                country_code TEXT, municipality TEXT, iata_code TEXT, keywords TEXT
            ) ON COMMIT DROP
        """)

        # 2. COPY CSV into staging table (fast bulk load)
        logger.info(f"Loading {CLEAN_CSV.name} into staging table via COPY...")
        async with conn.cursor() as cur:
            async with cur.copy(_COPY_STAGING_SQL) as copy:
                with open(CLEAN_CSV, "rb") as f:
                    await copy.write(f.read())

        # 3. UPSERT from staging into locations
        logger.info("Upserting from staging into locations...")
        _upsert_sql = f"""
            INSERT INTO locations (
                transport_mode, airport_size, name, latitude, longitude,
                continent, country_code, municipality, iata_code, keywords,
                natural_key
            )
            SELECT DISTINCT ON (nk)
                transport_mode::transportmodeenum, airport_size, name,
                latitude::float, longitude::float,
                continent, country_code, municipality, iata_code, keywords,
                nk AS natural_key
            FROM (
                SELECT *,
                    {_NATURAL_KEY_EXPR} AS nk
                FROM locations_staging
            ) deduped
            ORDER BY nk
            ON CONFLICT (natural_key) DO UPDATE SET
                name         = EXCLUDED.name,
                latitude     = EXCLUDED.latitude,
                longitude    = EXCLUDED.longitude,
                country_code = EXCLUDED.country_code,
                iata_code    = EXCLUDED.iata_code,
                airport_size = EXCLUDED.airport_size,
                continent    = EXCLUDED.continent,
                municipality = EXCLUDED.municipality,
                keywords     = EXCLUDED.keywords,
                natural_key  = EXCLUDED.natural_key
        """  # nosec B608 - constant expr, no user input
        await conn.execute(_upsert_sql)

        await conn.commit()

    logger.info("Location seeding complete!")


async def main() -> None:
    logger.info("Starting locations seeding...")
    await seed_locations()


if __name__ == "__main__":
    asyncio.run(main())
