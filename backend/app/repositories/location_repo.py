"""Location repository for database operations."""

from typing import List, Optional

from sqlalchemy import case
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
        Search locations by name with relevance ordering.

        Results are ordered by relevance:
        1. Exact matches (name = query)
        2. Starts with query (name ILIKE 'query%')
        3. Contains query (name ILIKE '%query%')

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 20)
            transport_mode: Filter by transport mode ('train' or 'plane').
            If None, returns both types.

        Returns:
            List of Location objects ordered by relevance
        """
        # Normalize query
        query = query.strip()
        if not query:
            return []

        # Build base query
        statement = select(Location).where(col(Location.name).ilike(f"%{query}%"))

        # Filter by transport_mode if provided
        if transport_mode:
            statement = statement.where(col(Location.transport_mode) == transport_mode)

        # Order by relevance using CASE expression
        # Priority: 1 = exact match, 2 = starts with, 3 = contains
        relevance = case(
            (col(Location.name) == query, 1),
            (col(Location.name).ilike(f"{query}%"), 2),
            else_=3,
        )

        statement = statement.order_by(relevance.asc(), col(Location.name).asc())
        statement = statement.limit(limit)

        # Execute query
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, location_id: int) -> Optional[Location]:
        """Get location by ID."""
        result = await self.session.get(Location, location_id)
        return result
