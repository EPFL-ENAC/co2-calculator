"""Location repository for database operations."""

from typing import List, Optional

from sqlalchemy import case, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.location import Location

logger = get_logger(__name__)


class LocationRepository:
    """Repository for Location database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_location(
        self,
        query: str,
        limit: int = 20,
        transport_mode: Optional[str] = None,
    ) -> List[Location]:
        """
        Search locations by keywords, municipality, and name with relevance ordering.

        Search is performed across:
        - keywords column
        - municipality column
        - name column

        For flights (transport_mode='plane'), results are prioritized by:
        1. large_airport first
        2. Then by relevance (exact match, starts with, contains)

        Results are ordered by relevance:
        1. Exact matches (field = query)
        2. Starts with query (field ILIKE 'query%')
        3. Contains query (field ILIKE '%query%')

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 20)
            transport_mode: Filter by transport mode ('train' or 'plane').
            If None, returns both types.

        Returns:
            List of Location objects ordered by relevance (and airport_size for flights)
        """
        # Normalize query
        query = query.strip()
        if not query:
            return []

        # Build search condition: search in keywords, municipality, and name
        search_pattern = f"%{query}%"
        search_condition = or_(
            col(Location.name).ilike(search_pattern),
            col(Location.municipality).ilike(search_pattern),
            col(Location.keywords).ilike(search_pattern),
        )

        # Build base query
        statement = select(Location).where(search_condition)

        # Filter by transport_mode if provided
        if transport_mode:
            statement = statement.where(col(Location.transport_mode) == transport_mode)

        # Calculate relevance score across all searchable fields
        # Priority: 1 = exact match, 2 = starts with, 3 = contains
        # We check all three fields and take the best match
        relevance = case(
            # Exact matches (highest priority)
            (
                or_(
                    col(Location.name) == query,
                    col(Location.municipality) == query,
                    col(Location.keywords) == query,
                ),
                1,
            ),
            # Starts with (medium priority)
            (
                or_(
                    col(Location.name).ilike(f"{query}%"),
                    col(Location.municipality).ilike(f"{query}%"),
                    col(Location.keywords).ilike(f"{query}%"),
                ),
                2,
            ),
            # Contains (lowest priority)
            else_=3,
        )

        # For flights, prioritize large_airport first
        if transport_mode == "plane":
            # Order by: airport_size (large_airport first), then relevance, then name
            airport_priority = case(
                (col(Location.airport_size) == "large_airport", 1),
                else_=2,
            )
            statement = statement.order_by(
                airport_priority.asc(),
                relevance.asc(),
                col(Location.name).asc(),
            )
        else:
            # For trains or mixed results, order by relevance then name
            statement = statement.order_by(relevance.asc(), col(Location.name).asc())

        statement = statement.limit(limit)

        # Execute query
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, location_id: int) -> Optional[Location]:
        """Get location by ID."""
        result = await self.session.get(Location, location_id)
        return result
