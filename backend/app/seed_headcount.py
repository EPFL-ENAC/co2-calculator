import asyncio
import csv
from datetime import datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.headcount import HeadCount

logger = get_logger(__name__)
settings = get_settings()


async def seed_headcount(session: AsyncSession) -> None:
    """Upsert headcount data from seed_headcount.csv."""
    logger.info("Upserting headcount data...")

    csv_path = Path(__file__).parent.parent / "seed_headcount.csv"
    if not csv_path.exists():
        logger.error(f"Headcount CSV file not found at {csv_path}")
        return

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        upserted = 0
        for row in reader:
            # Parse fields from CSV, adjust as needed to match your CSV columns
            date = row.get("date")
            if date:
                date = datetime.strptime(date, "%Y-%m-%d").date()
            else:
                logger.warning(f"Missing date in row: {row}")
                continue

            unit_id = row.get("unit_id")
            unit_name = row.get("unit_name")
            cf = row.get("cf")
            cf_name = row.get("cf_name")
            cf_user_id = row.get("cf_user_id")
            display_name = row.get("display_name")
            status = row.get("status")
            function = row.get("function")
            sciper = row.get("sciper")
            fte = float(row.get("fte", 0))
            submodule = row.get("submodule")
            provider = "csv"

            # Compose unique filter
            stmt = select(HeadCount).where(
                HeadCount.date == date,
                HeadCount.unit_id == unit_id,
                HeadCount.cf == cf,
                HeadCount.sciper == sciper,
            )
            result = await session.exec(stmt)
            existing = result.first()

            if existing:
                # Update all fields
                existing.unit_name = unit_name or ""
                existing.cf_name = cf_name or ""
                existing.cf_user_id = cf_user_id or ""
                existing.display_name = display_name or ""
                existing.status = status or ""
                existing.function = function or ""
                existing.fte = fte
                existing.submodule = submodule or ""
                existing.provider = provider
            else:
                # Insert new record
                headcount = HeadCount(
                    date=date,
                    unit_id=unit_id or "",
                    unit_name=unit_name or "",
                    cf=cf or "",
                    cf_name=cf_name or "",
                    cf_user_id=cf_user_id or "",
                    display_name=display_name or "",
                    status=status or "",
                    function=function or "",
                    sciper=sciper or "",
                    fte=fte,
                    submodule=submodule or "",
                    provider=provider,
                )
                session.add(headcount)
            upserted += 1

    await session.commit()
    logger.info(f"Upserted {upserted} headcount records from CSV")


async def main() -> None:
    """Main seed function."""
    logger.info("Starting equipment and emissions seeding...")

    async with SessionLocal() as session:
        await seed_headcount(session)

    logger.info("Equipment and emissions seeding complete!")


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
