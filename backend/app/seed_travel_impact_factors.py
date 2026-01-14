"""Seed travel impact factors (plane and train) from CSV data.

This script populates the plane_impact_factors and train_impact_factors tables
from CSV files.
"""

import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.travel_impact_factor import (
    PlaneImpactFactor,
    TrainImpactFactor,
)

logger = get_logger(__name__)


async def seed_plane_impact_factors(session: AsyncSession) -> None:
    """Seed plane impact factors from plane_impact_factors.csv."""
    logger.info("Seeding plane impact factors from CSV...")

    # Find the CSV file
    csv_path = Path(__file__).parent / "api" / "v1" / "plane_impact_factors.csv"
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    # Load existing factors into a dict keyed by category
    result = await session.exec(
        select(PlaneImpactFactor).where(col(PlaneImpactFactor.valid_to).is_(None))
    )
    existing_factors = {factor.category: factor for factor in result.all()}
    existing_count = len(existing_factors)
    logger.info(f"Found {existing_count} existing plane impact factors in database")

    # Set valid_from to current time
    valid_from = datetime.now(timezone.utc)

    # Read and parse CSV
    factors_to_insert = []
    skipped = 0
    updated_count = 0
    processed_count = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Parse category
                category = row.get("category", "").strip()
                if not category:
                    logger.warning(f"Row {row_num}: Missing category, skipping")
                    skipped += 1
                    continue

                # Validate category
                valid_categories = [
                    "very_short_haul",
                    "short_haul",
                    "medium_haul",
                    "long_haul",
                ]
                if category not in valid_categories:
                    logger.warning(
                        f"Row {row_num}: Invalid category '{category}', skipping"
                    )
                    skipped += 1
                    continue

                # Parse impact_score
                try:
                    impact_score = float(row.get("impact_score", "").strip())
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Row {row_num}: Invalid impact_score "
                        f"'{row.get('impact_score')}', skipping: {e}"
                    )
                    skipped += 1
                    continue

                # Parse rfi_adjustment
                try:
                    rfi_adjustment = float(row.get("rfi_adjustment", "").strip())
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Row {row_num}: Invalid rfi_adjustment "
                        f"'{row.get('rfi_adjustment')}', skipping: {e}"
                    )
                    skipped += 1
                    continue

                # Parse min_distance (optional, can be empty)
                min_distance = None
                min_distance_str = row.get("min_distance", "").strip()
                if min_distance_str:
                    try:
                        min_distance = float(min_distance_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Row {row_num}: Invalid min_distance "
                            f"'{min_distance_str}', skipping: {e}"
                        )
                        skipped += 1
                        continue

                # Parse max_distance (optional, can be empty)
                max_distance = None
                max_distance_str = row.get("max_distance", "").strip()
                if max_distance_str:
                    try:
                        max_distance = float(max_distance_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Row {row_num}: Invalid max_distance "
                            f"'{max_distance_str}', skipping: {e}"
                        )
                        skipped += 1
                        continue

                # Check if factor already exists
                existing_factor = existing_factors.get(category)

                if existing_factor:
                    # Update existing factor if values differ
                    if (
                        existing_factor.impact_score != impact_score
                        or existing_factor.rfi_adjustment != rfi_adjustment
                        or existing_factor.min_distance != min_distance
                        or existing_factor.max_distance != max_distance
                    ):
                        # Set valid_to on old factor
                        existing_factor.valid_to = valid_from
                        session.add(existing_factor)

                        # Create new factor
                        new_factor = PlaneImpactFactor(
                            factor_type="plane",
                            category=category,
                            impact_score=impact_score,
                            rfi_adjustment=rfi_adjustment,
                            min_distance=min_distance,
                            max_distance=max_distance,
                            valid_from=valid_from,
                            valid_to=None,
                        )
                        factors_to_insert.append(new_factor)
                        updated_count += 1
                        processed_count += 1
                else:
                    # Create new factor
                    factor = PlaneImpactFactor(
                        factor_type="plane",
                        category=category,
                        impact_score=impact_score,
                        rfi_adjustment=rfi_adjustment,
                        min_distance=min_distance,
                        max_distance=max_distance,
                        valid_from=valid_from,
                        valid_to=None,
                    )
                    factors_to_insert.append(factor)
                    processed_count += 1

            except Exception as e:
                logger.error(f"Row {row_num}: Error processing row: {e}")
                logger.debug(f"Row data: {row}")
                skipped += 1
                continue

    logger.info(
        f"Processed {processed_count} rows from CSV, "
        f"prepared {len(factors_to_insert)} to insert, "
        f"{updated_count} to update, {skipped} skipped"
    )

    # Insert new factors and commit all changes (updates + inserts)
    total_inserted = 0
    if factors_to_insert:
        session.add_all(factors_to_insert)
        total_inserted = len(factors_to_insert)
        logger.debug(f"Added {total_inserted} plane factors to session")

    # Commit if there are any changes (updates or inserts)
    if factors_to_insert or updated_count > 0:
        try:
            await session.flush()  # Flush to catch any constraint errors early
            await session.commit()
            if total_inserted > 0:
                logger.info(f"Inserted {total_inserted} new plane impact factors")
            if updated_count > 0:
                logger.info(f"Updated {updated_count} existing plane impact factors")
        except Exception as e:
            logger.error(f"Error committing plane impact factors: {e}", exc_info=True)
            await session.rollback()
            raise
    else:
        logger.info("No changes to commit - all factors already exist with same values")

    logger.info(
        f"Plane impact factor seeding complete! "
        f"Inserted {total_inserted} new factors, "
        f"updated {updated_count} existing factors, "
        f"skipped {skipped} rows"
    )


async def seed_train_impact_factors(session: AsyncSession) -> None:
    """Seed train impact factors from train_impact_factors.csv."""
    logger.info("Seeding train impact factors from CSV...")

    # Find the CSV file
    csv_path = Path(__file__).parent / "api" / "v1" / "train_impact_factors.csv"
    logger.debug(f"Looking for train impact factors CSV at: {csv_path}")
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        logger.error(f"Absolute path: {csv_path.resolve()}")
        parent_dir = Path(__file__).parent.parent / "api" / "v1"
        logger.error(f"Parent directory contents: {list(parent_dir.iterdir())}")
        return
    logger.info(f"Found train impact factors CSV at: {csv_path}")

    # Load existing factors into a dict keyed by countrycode
    try:
        result = await session.exec(
            select(TrainImpactFactor).where(col(TrainImpactFactor.valid_to).is_(None))
        )
        existing_factors = {factor.countrycode: factor for factor in result.all()}
        existing_count = len(existing_factors)
        logger.info(f"Found {existing_count} existing train impact factors in database")
    except Exception as e:
        logger.error(
            f"Error loading existing train impact factors. "
            f"Make sure the train_impact_factors table exists and has all "
            f"required columns. Error: {e}"
        )
        logger.info("Continuing with empty existing factors list...")
        existing_factors = {}
        existing_count = 0

    # Set valid_from to current time
    valid_from = datetime.now(timezone.utc)

    # Read and parse CSV
    factors_to_insert = []
    skipped = 0
    updated_count = 0
    processed_count = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        logger.debug(f"CSV headers: {reader.fieldnames}")
        row_count = 0
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            row_count += 1
            logger.debug(f"Processing row {row_num}: {row}")
            try:
                # Parse countrycode
                countrycode = row.get("countrycode", "").strip()
                if not countrycode:
                    logger.warning(
                        f"Row {row_num}: Missing countrycode, skipping. Row data: {row}"
                    )
                    skipped += 1
                    continue

                # Parse impact_score
                try:
                    impact_score = float(row.get("impact_score", "").strip())
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Row {row_num}: Invalid impact_score "
                        f"'{row.get('impact_score')}', skipping: {e}"
                    )
                    skipped += 1
                    continue

                # Check if factor already exists
                existing_factor = existing_factors.get(countrycode)
                logger.debug(
                    f"Row {row_num}: countrycode='{countrycode}', "
                    f"impact_score={impact_score}, "
                    f"existing={existing_factor is not None}"
                )

                if existing_factor:
                    # Update existing factor if value differs
                    if existing_factor.impact_score != impact_score:
                        logger.debug(
                            f"Updating train factor for {countrycode}: "
                            f"{existing_factor.impact_score} -> {impact_score}"
                        )
                        # Set valid_to on old factor
                        existing_factor.valid_to = valid_from
                        session.add(existing_factor)

                        # Create new factor
                        new_factor = TrainImpactFactor(
                            countrycode=countrycode,
                            impact_score=impact_score,
                            valid_from=valid_from,
                            valid_to=None,
                        )
                        factors_to_insert.append(new_factor)
                        updated_count += 1
                        processed_count += 1
                    else:
                        logger.debug(
                            f"Skipping {countrycode}: same impact_score "
                            f"({impact_score})"
                        )
                else:
                    # Create new factor
                    logger.debug(f"Creating new train factor for {countrycode}")
                    factor = TrainImpactFactor(
                        countrycode=countrycode,
                        impact_score=impact_score,
                        valid_from=valid_from,
                        valid_to=None,
                    )
                    factors_to_insert.append(factor)
                    processed_count += 1

            except Exception as e:
                logger.error(f"Row {row_num}: Error processing row: {e}")
                logger.debug(f"Row data: {row}")
                skipped += 1
                continue

    logger.info(
        f"Read {row_count} rows from CSV. "
        f"Processed {processed_count} rows, "
        f"prepared {len(factors_to_insert)} to insert, "
        f"{updated_count} to update, {skipped} skipped"
    )

    if row_count == 0:
        logger.warning("No rows found in train_impact_factors.csv file!")
        return

    # Insert new factors and commit all changes (updates + inserts)
    total_inserted = 0
    if factors_to_insert:
        session.add_all(factors_to_insert)
        total_inserted = len(factors_to_insert)
        logger.debug(f"Added {total_inserted} train factors to session")

    # Commit if there are any changes (updates or inserts)
    if factors_to_insert or updated_count > 0:
        try:
            await session.flush()  # Flush to catch any constraint errors early
            await session.commit()
            if total_inserted > 0:
                logger.info(f"Inserted {total_inserted} new train impact factors")
            if updated_count > 0:
                logger.info(f"Updated {updated_count} existing train impact factors")
        except Exception as e:
            logger.error(f"Error committing train impact factors: {e}", exc_info=True)
            await session.rollback()
            raise
    else:
        logger.info("No changes to commit - all factors already exist with same values")

    logger.info(
        f"Train impact factor seeding complete! "
        f"Inserted {total_inserted} new factors, "
        f"updated {updated_count} existing factors, "
        f"skipped {skipped} rows"
    )


async def seed_travel_impact_factors(session: AsyncSession) -> None:
    """Seed both plane and train impact factors."""
    await seed_plane_impact_factors(session)
    await seed_train_impact_factors(session)


async def main() -> None:
    """Main seed function."""
    logger.info("Starting travel impact factors seeding...")

    async with SessionLocal() as session:
        await seed_travel_impact_factors(session)

    logger.info("Travel impact factors seeding complete!")


if __name__ == "__main__":
    # Run script on CSV files in /app/api/v1/
    asyncio.run(main())
