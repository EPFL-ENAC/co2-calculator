from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
from sqlmodel import Session, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.unit import Unit
from app.models.user import UserProvider

"""
Unit provider interface and implementations.

Flow: 
Fetch roles from role_provider
Extract unit IDs from roles
 - For each unit ID, fetch full unit details from unit_provider
 - Upsert units with complete metadata (name, principal, path_name (affiliations)
  , visibility)
Create/update unit_users associations with role info

"""

logger = get_logger(__name__)
settings = get_settings()


class UnitProvider(ABC):
    """Abstract base class for unit providers."""

    type: UserProvider = UserProvider.DEFAULT

    async def fetch_all_units(self) -> tuple[list[dict], list[dict]]:
        """Fetch all units from the provider and return raw data as list of dicts."""
        raise NotImplementedError("fetch_all_units must be implemented by subclasses")

    def map_api_unit(self, unit_raw: dict) -> Unit:
        """Map a raw API unit dict to Unit field values."""
        raise NotImplementedError("map_api_unit must be implemented by subclasses")

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
        Get a single unit by ID, here the unit_id is the institutional_id.

        Args:
            unit_id: Unit ID to fetch

        Returns:
            Unit object or None if not found
        """
        units = await self.get_units(unit_ids=[unit_id])
        return units[0] if units else None


class DefaultUnitProvider(UnitProvider):
    type: UserProvider = UserProvider.DEFAULT
    """Default unit provider that reads from the database."""

    def __init__(self, db_session: Session | AsyncSession):
        self.db_session = db_session

    async def get_units(self, unit_ids: Optional[List[str]] = None) -> List[Unit]:
        from sqlmodel.ext.asyncio.session import AsyncSession

        statement = select(Unit)
        if unit_ids:
            statement = statement.where(col(Unit.id).in_(unit_ids))
        if isinstance(self.db_session, AsyncSession):
            results = await self.db_session.exec(statement)
        else:
            results = self.db_session.exec(statement)
        units = results.all()
        return list(units)


class AccredUnitProvider(UnitProvider):
    type: UserProvider = UserProvider.ACCRED
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

    async def fetch_all_units(self) -> tuple[list[dict], list[dict]]:
        if not all([self.api_url, self.api_username, self.api_key]):
            logger.error("Cannot fetch units: Accred API not configured")
            return [], []

        all_units: list[dict] = []
        all_principal_users: list[dict] = []
        seen_users: set[tuple[str, str]] = set()

        page = 1
        page_size = 100
        total = None  # we don't know it yet

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"{self.api_url}/units",
                    params={"pageindex": page, "pagesize": page_size},
                    auth=(self.api_username, self.api_key),
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                if total is None:
                    total = data["count"]
                    logger.info("Starting unit fetch", extra={"total": total})

                batch = data.get("units", [])
                if not batch:
                    break  # defensive stop

                all_units.extend(batch)

                for unit in batch:
                    responsible = unit.get("responsible")
                    if not responsible:
                        continue

                    email = responsible.get("email")
                    institutional_id = responsible.get("id")

                    if not email or not institutional_id:
                        continue

                    key = (email, institutional_id)
                    if key not in seen_users:
                        seen_users.add(key)
                        all_principal_users.append(responsible)

                logger.info(
                    "Fetched units page",
                    extra={
                        "page": page,
                        "total_so_far": len(all_units),
                    },
                )

                # Stop condition
                if len(all_units) >= total:
                    break

                page += 1

        logger.info("Finished fetching all units", extra={"total": len(all_units)})

        return all_units, all_principal_users

    def map_api_unit(self, unit_raw: dict) -> Unit:
        """Map a raw API unit dict to Unit field values."""
        cf = unit_raw.get("cf") or None
        ancestors = unit_raw.get(
            "ancestors", []
        )  # already ordered root→leaf, excludes self

        def get_parent_institutional_id(level: int, unit_raw: dict) -> Optional[str]:
            if level <= 1:
                return None
            return unit_raw.get(
                f"level{level}cf", None
            )  # parent is last in ancestors list

        return Unit(
            id=None,
            provider=UserProvider.ACCRED,
            institutional_code=str(unit_raw["id"]),
            institutional_id=cf if cf and cf != "0" else None,
            name=unit_raw["name"],
            label_fr=unit_raw.get("labelfr") or None,
            label_en=unit_raw.get("labelen") or None,
            level=unit_raw["level"],
            parent_institutional_code=unit_raw.get("parentid"),
            parent_institutional_id=get_parent_institutional_id(
                unit_raw["level"], unit_raw
            ),
            path_institutional_code=" ".join(ancestors + [str(unit_raw["id"])]),
            path_institutional_id=unit_raw.get("pathcf") or None,
            path_name=unit_raw.get("path") or None,
            unit_type_id=unit_raw.get("unittypeid"),
            unit_type_label=unit_raw.get("unittype", {}).get("label")
            if unit_raw.get("unittype")
            else None,
            principal_user_institutional_id=unit_raw.get("responsibleid", None),
            is_active=unit_raw.get("enddate", "") == "0001-01-01T00:00:00Z",
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
                # Extract principal information from responsible object
                # responsible_info = unit_data.get("responsible", {})
                # principal_user_institutional_id = responsible_info.get("id")
                units.append(self.map_api_unit(unit_data))

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
                extra={
                    "unit_ids": unit_ids,
                    "error": str(e),
                    "type": type(e).__name__,
                },
            )
            logger.exception("Unexpected error fetching units from Accred API")
            raise


class TestUnitProvider(UnitProvider):
    """Test unit provider for development."""

    type: UserProvider = UserProvider.TEST

    async def get_units(self, unit_ids: Optional[List[str]] = None) -> List[Unit]:
        """Return test units for development."""
        all_test_units = [
            Unit(
                id=1,
                provider=self.type,
                institutional_code="12345",
                institutional_id="1119",
                name="ENAC-IT4R-TEST",
                level=4,
                principal_user_institutional_id="testuser_co2.user.principal",
                path_institutional_code="10582 10583 11435",
                path_institutional_id="cf-10582 cf-10583 cf-11435",
                path_name="EPFL ENAC IT4R-TEST",
            ),
            Unit(
                id=2,
                provider=self.type,
                institutional_code="67890",
                name="IC-TEST",
                level=3,
                principal_user_institutional_id="testuser_co2.user.principal",
                path_institutional_code="10582 10583 11436",
                path_institutional_id="cf-10582 cf-10583 cf-11436",
                path_name="EPFL IC-TEST",
            ),
        ]

        if unit_ids:
            return [
                Unit(
                    provider=self.type,
                    institutional_code=str(unit_id),
                    name=f"I-{unit_id}-TEST",
                    level=4,
                    path_institutional_code=f"10582 10583 {unit_id}",
                    path_institutional_id=f"cf-10582 cf-10583 cf-{unit_id}",
                    principal_user_institutional_id="testuser_co2.user.principal",
                    path_name=f"TEST-AFFILIATION-{unit_id}",
                )
                for unit_id in unit_ids
            ]
        return all_test_units


def get_unit_provider(
    provider_type: UserProvider | None = None,
    db_session: Session | AsyncSession | None = None,
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

    if provider_type == UserProvider.DEFAULT:
        logger.info("Using DefaultUnitProvider (Database)")
        if not db_session:
            raise ValueError("DefaultUnitProvider requires a database session")
        return DefaultUnitProvider(db_session)
    elif provider_type == UserProvider.ACCRED:
        logger.info("Using AccredUnitProvider (EPFL Accred API)")
        return AccredUnitProvider()
    elif provider_type == UserProvider.TEST:
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
