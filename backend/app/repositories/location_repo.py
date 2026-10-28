"""Location repository for database operations."""

import logging
import re

from sqlalchemy import ColumnElement
from sqlmodel import case, col, func, or_, select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.location import LOCATION_SEARCH_COLUMNS, Location, TransportModeEnum

logger = logging.getLogger(__name__)


def _word_matches(word: str) -> ColumnElement[bool]:
    """``word`` appears in one of the search columns, ignoring case and accents.

    Words of 1-2 letters match a word start ("be" finds Bern, not Oberhausen);
    longer words match anywhere ("bahnhof" in Hauptbahnhof). Both patterns keep
    a trigram, so the ``ix_locations_*_trgm`` indexes on ``search_text()`` serve
    them.
    """
    pattern = f"%{word}%"
    if len(word) < 3:
        pattern = f"% {word}%"
    folded = func.unaccent(pattern)
    return or_(
        *(
            func.search_text(col(getattr(Location, column))).ilike(folded)
            for column in LOCATION_SEARCH_COLUMNS
        )
    )


class LocationRepository:
    """Repository for Location database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_location(
        self,
        query: str,
        transport_mode: TransportModeEnum,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Location]:
        """Search locations by keywords, municipality, iata and name with
        relevance ordering.

        Search is performed across:
        - keywords column
        - municipality column
        - iata_code column
        - name column

        The query is split into words; a location matches when every word
        appears in one of those columns, ignoring case and accents. Words of
        1-2 letters must start a word, longer ones may appear anywhere.

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
            offset: Number of ranked results to skip, for pagination
            transport_mode: Filter by location transport mode ('train' or 'plane').

        Returns:
            List of Location objects ordered by country (Switzerland first),
            relevance, and airport_size (for airport searches)
        """
        query = query.strip()

        # Every word must appear somewhere, so separators, word order and accents
        # don't matter: "geneve aeroport" finds "Genève-Aéroport".
        words = re.findall(r"[^\W_]+", query)
        if not words:
            return []
        statement = select(Location).where(*(_word_matches(word) for word in words))

        # Filter by location transport_mode
        if transport_mode:
            statement = statement.where(col(Location.transport_mode) == transport_mode)

        # Relevance for ordering: trigram similarity (0..1), case-folded by pg_trgm.
        relevance_score = case(
            # Exact matches get highest score (1.0)
            (text("unaccent(LOWER(name)) = unaccent(LOWER(:exact_query))"), 1.0),
            # Similarity scores for partial matches
            else_=text("""
                GREATEST(
                    COALESCE(similarity(unaccent(name), unaccent(:query)), 0),
                    COALESCE(similarity(unaccent(iata_code), unaccent(:query)), 0),
                    COALESCE(similarity(unaccent(municipality), unaccent(:query)), 0),
                    COALESCE(similarity(unaccent(keywords), unaccent(:query)), 0)
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
                # Accents are folded to match; the spelling typed ranks first
                text("similarity(name, :query) DESC"),
                col(Location.name).asc(),
                # Names repeat, so id keeps the order total and pages disjoint
                col(Location.id).asc(),
            )
        else:
            # For train searches, order by Switzerland first, then relevance
            extended = extended.order_by(
                switzerland_priority.asc(),
                text("relevance DESC"),  # Higher similarity scores first
                text("similarity(name, :query) DESC"),
                col(Location.name).asc(),
                col(Location.id).asc(),
            )

        extended = extended.offset(offset).limit(limit)

        # Strip newlines so a crafted query can't forge extra log lines
        safe_query = query.replace("\r", "").replace("\n", "")
        try:
            compiled = extended.compile(compile_kwargs={"literal_binds": False})
            logger.debug(f"Location search SQL: {compiled}")

            result = await self.session.execute(extended)
            # Since we added a relevance column, extract just the Location objects
            locations = [row[0] for row in result.fetchall()]

            logger.debug(f"Found {len(locations)} locations for query '{safe_query}'")
            return locations
        except Exception as e:
            logger.error(
                f"Error executing location search query for '{safe_query}'. Error: {e}",
                exc_info=True,
            )
            raise

    async def get_by_id(self, location_id: int) -> Location | None:
        """Get location by ID."""
        result = await self.session.get(Location, location_id)
        return result

    async def get_by_natural_key(self, natural_key: str) -> Location | None:
        """Get location by natural_key (unique index — always unambiguous)."""
        statement = select(Location).where(col(Location.natural_key) == natural_key)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_iata(self, iata_code: str) -> Location | None:
        """Get location by IATA code."""
        statement = select(Location).where(col(Location.iata_code) == iata_code)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_iata_codes(self, iata_codes: list[str]) -> list[Location]:
        """Bulk-fetch locations for a set of IATA codes in one query.

        Lets the recalc slice resolve every flight's airports up front
        instead of two point lookups per entry. Empty input short-circuits.
        """
        if not iata_codes:
            return []
        statement = select(Location).where(col(Location.iata_code).in_(iata_codes))
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def find_train_stations_by_name(
        self,
        name: str,
        country_code: str,
        limit: int = 2,
    ) -> list[Location]:
        """Exact-match train station lookup by name within a country.

        Case-insensitive on the lowercased+trimmed name. Used by the CSV
        ingestion resolver to map ``origin_name`` → a single ``Location``,
        so the caller only needs to distinguish 0 / 1 / many matches —
        ``limit=2`` is the cheapest way to do that.
        """
        normalized = name.strip().lower()
        statement = (
            select(Location)
            .where(col(Location.transport_mode) == TransportModeEnum.train)
            .where(text("lower(trim(name)) = :name").bindparams(name=normalized))
            .where(col(Location.country_code) == country_code)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
