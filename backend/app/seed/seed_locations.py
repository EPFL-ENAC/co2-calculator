"""Seed locations (train stations and airports) via PostgreSQL COPY.

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

_COPY_COLUMNS = (
    "transport_mode, airport_size, name, latitude, longitude, "
    "continent, country_code, municipality, iata_code, keywords"
)
_COPY_SQL = f"COPY locations ({_COPY_COLUMNS}) FROM STDIN CSV HEADER NULL ''"


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
        logger.info("Truncating locations table...")
        await conn.execute("TRUNCATE TABLE locations RESTART IDENTITY")

        logger.info(f"Loading {CLEAN_CSV.name} via COPY...")
        async with conn.cursor() as cur:
            async with cur.copy(_COPY_SQL) as copy:
                with open(CLEAN_CSV, "rb") as f:
                    await copy.write(f.read())

        await conn.commit()

    logger.info("Location seeding complete!")


async def main() -> None:
    logger.info("Starting locations seeding...")
    await seed_locations()


if __name__ == "__main__":
    asyncio.run(main())
