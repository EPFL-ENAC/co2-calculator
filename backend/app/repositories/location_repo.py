"""Location repository for database operations."""

from typing import List, Optional

from sqlalchemy import bindparam, case, or_, text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.location import Location, TransportModeEnum

logger = get_logger(__name__)


class LocationRepository:
    """Repository for Location database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_location(
        self,
        query: str,
        transport_mode: TransportModeEnum,
        limit: int = 20,
    ) -> List[Location]:
        """
        Search locations by keywords, municipality, iata and name with
        relevance ordering.

        Search is performed across:
        - keywords column
        - municipality column
        - iata_code column
        - name column

        Search uses PostgreSQL trigram similarity for efficient pattern matching.

        Results are prioritized by:
        1. Switzerland (country_code == "CH") first
        2. For airports (location transport_mode='plane'): large_airport first
        3. Then by relevance (exact match, starts with, contains)

        Results are ordered by relevance:
        1. Exact matches (field = query)
        2. Starts with query (field ILIKE 'query%')
        3. Contains query (field ILIKE '%query%')

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 20)
            transport_mode: Filter by location transport mode ('train' or 'plane').

        Returns:
            List of Location objects ordered by country (Switzerland first),
            relevance, and airport_size (for airport searches)
        """

        query = query.strip()
        if not query:
            return []

        statement = select(Location)

        # Use PostgreSQL trigram similarity for efficient searching
        # This works with our GIN indexes using gin_trgm_ops
        search_condition = or_(
            text("LOWER(name) % LOWER(:query)").bindparams(bindparam("query", query)),
            text("LOWER(iata_code) % LOWER(:query)").bindparams(
                bindparam("query", query)
            ),
            text("LOWER(municipality) % LOWER(:query)").bindparams(
                bindparam("query", query)
            ),
            text("LOWER(keywords) % LOWER(:query)").bindparams(
                bindparam("query", query)
            ),
        )

        statement = statement.where(search_condition)

        # Filter by location transport_mode
        if transport_mode:
            statement = statement.where(col(Location.transport_mode) == transport_mode)

        # Calculate numeric relevance score using trigram similarity.
        # The % operator above is only a boolean threshold match filter; similarity()
        # returns the 0..1 score used here for ordering.
        relevance_score = case(
            # Exact matches get highest score (1.0)
            (text("LOWER(name) = LOWER(:exact_query)"), 1.0),
            # Similarity scores for partial matches
            else_=text("""
                GREATEST(
                    COALESCE(similarity(LOWER(name), LOWER(:query)), 0),
                    COALESCE(similarity(LOWER(iata_code), LOWER(:query)), 0),
                    COALESCE(similarity(LOWER(municipality), LOWER(:query)), 0),
                    COALESCE(similarity(LOWER(keywords), LOWER(:query)), 0)
                )
            """),
        ).label("relevance")

        # Add relevance score to select (use separate var to preserve base type)
        extended = statement.add_columns(relevance_score)

        # Bind parameters for relevance calculation
        extended = extended.params(exact_query=query, query=query)

        # Prioritize Switzerland
        switzerland_priority = case(
            (col(Location.country_code) == "CH", 1),
            else_=2,
        )

        # For airport searches, prioritize large_airport first
        if transport_mode == TransportModeEnum.plane:
            airport_priority = case(
                (col(Location.airport_size) == "large_airport", 1),
                else_=2,
            )
            extended = extended.order_by(
                switzerland_priority.asc(),
                airport_priority.asc(),
                text("relevance DESC"),  # Higher similarity scores first
                col(Location.name).asc(),
            )
        else:
            # For train searches, order by Switzerland first, then relevance
            extended = extended.order_by(
                switzerland_priority.asc(),
                text("relevance DESC"),  # Higher similarity scores first
                col(Location.name).asc(),
            )

        extended = extended.limit(limit)

        try:
            compiled = extended.compile(compile_kwargs={"literal_binds": False})
            logger.debug(f"Location search SQL: {compiled}")

            result = await self.session.execute(extended)
            # Since we added a relevance column, extract just the Location objects
            locations = [row[0] for row in result.fetchall()]

            logger.debug(f"Found {len(locations)} locations for query '{query}'")
            return locations
        except Exception as e:
            logger.error(
                f"Error executing location search query for '{query}'. Error: {e}",
                exc_info=True,
            )
            raise

    async def get_by_id(self, location_id: int) -> Optional[Location]:
        """Get location by ID."""
        result = await self.session.get(Location, location_id)
        return result

    async def get_by_name(self, name: str) -> Optional[Location]:
        """Get location by name."""
        statement = select(Location).where(col(Location.name) == name)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_iata(self, iata_code: str) -> Optional[Location]:
        """Get location by IATA code."""
        statement = select(Location).where(col(Location.iata_code) == iata_code)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
