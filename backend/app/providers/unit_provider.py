from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.unit import Unit

"""
Unit provider interface and implementations.

Flow: 
Fetch roles from role_provider
Extract unit IDs from roles
 - For each unit ID, fetch full unit details from unit_provider
 - Upsert units with complete metadata (name, principal, affiliations, visibility)
Create/update unit_users associations with role info

"""

logger = get_logger(__name__)
settings = get_settings()


class UnitProvider(ABC):
    """Abstract base class for unit providers."""

    type: str = "abstract"

    @abstractmethod
    async def get_units(self, unit_ids: Optional[List[str]] = None) -> List[Unit]:
        """
        Get units, optionally filtered by unit_ids.

        Args:
            unit_ids: Optional list of unit IDs to filter by. If None, return all.

        Returns:
            List of Unit objects with full metadata
        """
        pass

    async def get_unit_by_id(self, unit_id: str) -> Optional[Unit]:
        """
        Get a single unit by ID.

        Args:
            unit_id: Unit ID to fetch

        Returns:
            Unit object or None if not found
        """
        units = await self.get_units(unit_ids=[unit_id])
        return units[0] if units else None


class DefaultUnitProvider(UnitProvider):
    type: str = "default"

    def __init__(self, db_session: Session):
        self.db_session = db_session

    async def get_units(self, unit_ids: Optional[List[str]] = None) -> List[Unit]:
        statement = select(Unit)
        if unit_ids:
            statement = statement.where(col(Unit.id).in_(unit_ids))
        results = self.db_session.exec(statement)
        units = results.all()
        return list(units)


class AccredUnitProvider(UnitProvider):
    type: str = "accred"
    """Accred unit provider that fetches units from EPFL Accred API.

    Calls the EPFL Accred units endpoint to fetch unit details
    and maps them to CO2 application Unit model.
    """

    def __init__(self):
        """Initialize the Accred provider with API credentials."""
        self.api_url = settings.ACCRED_API_URL
        self.api_username = settings.ACCRED_API_USERNAME
        self.api_key = settings.ACCRED_API_KEY

        if not all([self.api_url, self.api_username, self.api_key]):
            logger.warning(
                "Accred API credentials not fully configured. "
                "Set ACCRED_API_URL, ACCRED_API_USERNAME, and ACCRED_API_KEY."
            )

    async def get_units(self, unit_ids: Optional[List[str]] = None) -> List[Unit]:
        """Fetch units from EPFL Accred API.

        Args:
            unit_ids: Optional list of unit IDs to filter by. If None, return all.

        Returns:
            List of Unit objects with full metadata
        """
        if not all([self.api_url, self.api_username, self.api_key]):
            logger.error("Cannot fetch units: Accred API not configured")
            return []

        try:
            # Call EPFL Accred units endpoint
            url = f"{self.api_url}/units"
            params: dict[str, str | int] = {}

            if unit_ids:
                # Convert list to comma-separated string for API
                params["ids"] = ",".join(unit_ids)
                params["pagesize"] = len(unit_ids)
            else:
                # If no specific IDs, you may need pagination logic
                logger.warning(
                    "Fetching all units without filter - may require pagination"
                )

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params,
                    auth=(self.api_username, self.api_key),
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            unit_data_list = data.get("units", [])

            if not unit_data_list:
                logger.info(
                    "No units found in Accred API",
                    extra={"unit_ids": unit_ids},
                )
                return []

            # Map API response to Unit objects
            units: List[Unit] = []
            for unit_data in unit_data_list:
                unit_id = str(unit_data.get("id"))
                unit_name = unit_data.get("name", "")
                cf = unit_data.get("cf", "")

                # Extract principal information from responsible object
                responsible_info = unit_data.get("responsible", {})
                principal_user_id = responsible_info.get("id")
                principal_user_name = responsible_info.get("display")
                principal_user_email = responsible_info.get("email")
                principal_user_function = "head"

                # Extract affiliations from path (space-separated hierarchy)
                affiliations = []
                path = unit_data.get("path", "")
                if path:
                    # path is space-separated like "EPFL ENAC ENAC-SG ENAC-IT"
                    affiliations = [
                        part.strip() for part in path.split(" ") if part.strip()
                    ]

                units.append(
                    Unit(
                        id=unit_id,
                        name=unit_name,
                        cf=cf,
                        principal_user_id=principal_user_id,
                        principal_user_function=principal_user_function,
                        principal_user_name=principal_user_name,
                        principal_user_email=principal_user_email,
                        affiliations=affiliations,
                        visibility="private",  # Default visibility
                    )
                )

            logger.info(
                "Fetched units from Accred API",
                extra={
                    "requested_ids": unit_ids,
                    "units_found": len(units),
                },
            )

            return units

        except httpx.HTTPStatusError as e:
            logger.error(
                "Accred API HTTP error",
                extra={
                    "unit_ids": unit_ids,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "Accred API request error",
                extra={"unit_ids": unit_ids, "error": str(e)},
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error fetching units from Accred API",
                extra={"unit_ids": unit_ids, "error": str(e), "type": type(e).__name__},
            )
            logger.exception("Unexpected error fetching units from Accred API")
            raise


class TestUnitProvider(UnitProvider):
    type: str = "test"

    async def get_units(self, unit_ids: Optional[List[str]] = None) -> List[Unit]:
        """Return test units for development."""
        all_test_units = [
            Unit(
                id="12345",
                name="ENAC-IT4R",
                principal_user_id="testuser_co2.user.principal",
                principal_user_function="Professor",
                affiliations=["ENAC", "ENAC-IT"],
                visibility="private",
            ),
            Unit(
                id="67890",
                name="IC-TEST",
                principal_user_id="testuser_co2.user.principal",
                principal_user_function="Lab Manager",
                affiliations=["IC"],
                visibility="public",
            ),
        ]

        if unit_ids:
            return [u for u in all_test_units if u.id in unit_ids]
        return all_test_units


def get_unit_provider(
    provider_type: str | None = None, db_session: Session | None = None
) -> UnitProvider:
    """Factory function to get the configured unit provider.

    Args:
        provider_type: Optional provider type override
        db_session: Database session for DefaultUnitProvider

    Returns:
        UnitProvider instance
    """
    if not provider_type:
        provider_type = settings.PROVIDER_PLUGIN

    if provider_type == "default":
        logger.info("Using DefaultUnitProvider (Database)")
        if not db_session:
            raise ValueError("DefaultUnitProvider requires a database session")
        return DefaultUnitProvider(db_session)
    elif provider_type == "accred":
        logger.info("Using AccredUnitProvider (EPFL Accred API)")
        return AccredUnitProvider()
    elif provider_type == "test":
        logger.info("Using TestUnitProvider (for testing)")
        return TestUnitProvider()
    else:
        logger.error(
            "Unknown unit provider type, falling back to default",
            extra={"provider_type": provider_type},
        )
        if not db_session:
            raise ValueError("DefaultUnitProvider requires a database session")
        return DefaultUnitProvider(db_session)
