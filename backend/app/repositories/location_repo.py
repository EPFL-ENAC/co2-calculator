"""Location repository for database operations."""

from typing import List, Type, cast

from sqlalchemy import bindparam, case, or_, text
from sqlalchemy.sql.elements import BindParameter
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.location import (
    Location,
    PlaneLocation,
    TrainLocation,
    TransportModeEnum,
)

logger = get_logger(__name__)


class LocationRepository:
    """Repository for Location database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _model_for_mode(
        mode: TransportModeEnum,
    ) -> Type[PlaneLocation] | Type[TrainLocation]:
        return PlaneLocation if mode == TransportModeEnum.plane else TrainLocation

    @staticmethod
    def _to_location(
        row: PlaneLocation | TrainLocation, mode: TransportModeEnum
    ) -> Location:
        return Location(
            id=row.id or 0,
            name=row.name,
            airport_size=row.airport_size,
            latitude=row.latitude,
            longitude=row.longitude,
            continent=row.continent,
            country_code=row.country_code,
            iata_code=row.iata_code,
            municipality=row.municipality,
            keywords=row.keywords,
        )

    async def search_location(
        self,
        query: str,
        mode: TransportModeEnum,
        limit: int = 20,
    ) -> List[Location]:
        """
        Search locations by keywords, municipality, and name with relevance ordering.

        Search is performed across:
        - keywords column
        - municipality column
        - name column

        Search is accent-insensitive and case-insensitive using PostgreSQL ICU
        collations.

        Results are prioritized by:
        1. Switzerland (country_code == "CH") first
        2. For airports (plane): large_airport first
        3. Then by relevance (exact match, starts with, contains)

        Results are ordered by relevance:
        1. Exact matches (field = query)
        2. Starts with query (field ILIKE 'query%')
        3. Contains query (field ILIKE '%query%')

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 20)
            mode: Location mode ('train' or 'plane').

        Returns:
            List of Location objects ordered by country (Switzerland first),
            relevance, and airport_size (for airport searches)
        """

        query = query.strip()
        if not query:
            return []

        # Validate collation against whitelist to prevent injection
        allowed_collations = {"ch_fr_ci_ai", "ch_de_ci_ai", "ch_it_ci_ai"}
        collation = "ch_fr_ci_ai"
        if collation not in allowed_collations:
            raise ValueError(f"Invalid collation: {collation}")

        model = self._model_for_mode(mode)
        statement = select(model)

        search_pattern = f"%{query}%".lower()
        query_lower = query.lower()
        query_starts_pattern = f"{query}%".lower()

        table_name = model.__tablename__

        search_pattern_param: BindParameter[str] = bindparam(
            "search_pattern", search_pattern
        )
        query_exact_param: BindParameter[str] = bindparam("query_exact", query_lower)
        query_starts_param: BindParameter[str] = bindparam(
            "query_starts", query_starts_pattern
        )

        search_condition = or_(
            text(
                f"LOWER({table_name}.name COLLATE {collation}) LIKE :search_pattern"
            ).bindparams(search_pattern_param),
            text(
                f"LOWER({table_name}.municipality COLLATE {collation}) "
                f"LIKE :search_pattern"
            ).bindparams(search_pattern_param),
            text(
                f"LOWER({table_name}.keywords COLLATE {collation}) LIKE :search_pattern"
            ).bindparams(search_pattern_param),
        )

        statement = statement.where(search_condition)

        # Build relevance scoring using parameterized queries with collations
        # for accent-insensitive matching
        relevance = case(
            # Exact matches (highest priority) - accent-insensitive
            (
                or_(
                    text(
                        f"LOWER({table_name}.name COLLATE {collation}) = :query_exact"
                    ).bindparams(query_exact_param),
                    text(
                        f"LOWER({table_name}.municipality COLLATE {collation}) "
                        f"= :query_exact"
                    ).bindparams(query_exact_param),
                    text(
                        f"LOWER({table_name}.keywords COLLATE {collation}) "
                        f"= :query_exact"
                    ).bindparams(query_exact_param),
                ),
                1,
            ),
            # Starts with (medium priority) - accent-insensitive
            (
                or_(
                    text(
                        f"LOWER({table_name}.name COLLATE {collation}) "
                        f"LIKE :query_starts"
                    ).bindparams(query_starts_param),
                    text(
                        f"LOWER({table_name}.municipality COLLATE {collation}) "
                        f"LIKE :query_starts"
                    ).bindparams(query_starts_param),
                    text(
                        f"LOWER({table_name}.keywords COLLATE {collation}) "
                        f"LIKE :query_starts"
                    ).bindparams(query_starts_param),
                ),
                2,
            ),
            # Contains (lowest priority)
            else_=3,
        )

        # Prioritize Switzerland
        switzerland_priority = case(
            (col(model.country_code) == "CH", 1),
            else_=2,
        )

        # For airport searches, prioritize large_airport first
        if mode == TransportModeEnum.plane:
            airport_priority = case(
                (col(model.airport_size) == "large_airport", 1),
                else_=2,
            )
            statement = statement.order_by(
                switzerland_priority.asc(),
                airport_priority.asc(),
                relevance.asc(),
                col(model.name).asc(),
            )
        else:
            # For train searches, order by Switzerland first
            statement = statement.order_by(
                switzerland_priority.asc(),
                relevance.asc(),
                col(model.name).asc(),
            )

        statement = statement.limit(limit)

        try:
            compiled = statement.compile(compile_kwargs={"literal_binds": False})
            logger.debug(f"Location search SQL: {compiled}")

            result = await self.session.execute(statement)
            rows = list(result.scalars().all())
            locations = [
                self._to_location(cast(PlaneLocation | TrainLocation, row), mode)
                for row in rows
            ]
            logger.debug(f"Found {len(locations)} locations for query '{query}'")
            return locations
        except Exception as e:
            logger.error(
                f"Error executing location search query for '{query}'. "
                f"Collation {collation} may not exist or query syntax error. "
                f"Error: {e}",
                exc_info=True,
            )
            raise

    async def get_by_id(
        self, location_id: int, mode: TransportModeEnum
    ) -> Location | None:
        """Get location by ID constrained to the selected table/mode."""
        model = self._model_for_mode(mode)
        row = await self.session.get(model, location_id)
        if row is None:
            return None
        return self._to_location(cast(PlaneLocation | TrainLocation, row), mode)
