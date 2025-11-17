"""Role provider plugin system for flexible role management.

This module provides an abstract base class and implementations for fetching
user roles from different sources (JWT claims, EPFL Accred API, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RoleProvider(ABC):
    """Abstract base class for role providers.

    Role providers are responsible for fetching and transforming user roles
    from various sources into the standardized hierarchical format:
    [{"role": "co2.user.std", "on": {"unit": "12345"}}]
    """

    @abstractmethod
    async def get_roles(
        self, userinfo: Dict[str, Any], sciper: int
    ) -> List[Dict[str, Any]]:
        """Get roles for a user.

        Args:
            userinfo: OAuth userinfo dict from the identity provider
            sciper: EPFL SCIPER number of the user

        Returns:
            List of role dicts with structure:
            [{"role": "co2.user.std", "on": {"unit": "12345"}}]
            or [{"role": "co2.backoffice.admin", "on": "global"}]
        """
        pass


class DefaultRoleProvider(RoleProvider):
    """Default role provider that extracts roles from JWT claims.

    Expects roles in flat string format from JWT claims:
    - "co2.user.std@unit:12345" → {"role": "co2.user.std", "on": {"unit": "12345"}}
    - "co2.backoffice.admin@global" → {"role": "co2.backoffice.admin", "on": "global"}

    Roles without scope (bare strings) will be skipped with a warning.
    """

    async def get_roles(
        self, userinfo: Dict[str, Any], sciper: int
    ) -> List[Dict[str, Any]]:
        """Extract and parse roles from JWT claims.

        Args:
            userinfo: OAuth userinfo dict containing 'roles' claim
            sciper: EPFL SCIPER number (not used in default provider)

        Returns:
            List of parsed role dicts
        """
        jwt_roles = userinfo.get("roles", [])

        if not jwt_roles:
            logger.warning(
                "No roles found in JWT claims for user",
                extra={"sciper": sciper, "email": userinfo.get("email")},
            )
            return []

        parsed_roles = []

        for role_str in jwt_roles:
            if not isinstance(role_str, str):
                logger.warning(
                    "Invalid role format (not a string), skipping",
                    extra={"role": role_str, "sciper": sciper},
                )
                continue

            if "@" not in role_str:
                logger.warning(
                    "Role without scope (@), skipping",
                    extra={"role": role_str, "sciper": sciper},
                )
                continue

            # Parse "role@scope:value" format
            parts = role_str.split("@", 1)
            role_name = parts[0].strip()
            scope_part = parts[1].strip()

            if scope_part == "global":
                parsed_roles.append({"role": role_name, "on": "global"})
            elif ":" in scope_part:
                # Parse "unit:12345" → {"unit": "12345"}
                scope_type, scope_id = scope_part.split(":", 1)
                parsed_roles.append(
                    {
                        "role": role_name,
                        "on": {scope_type.strip(): scope_id.strip()},  # type: ignore
                    }
                )
            else:
                logger.warning(
                    "Invalid scope format, skipping",
                    extra={"role": role_str, "scope": scope_part, "sciper": sciper},
                )
                continue

        logger.info(
            "Parsed roles from JWT claims",
            extra={
                "sciper": sciper,
                "raw_count": len(jwt_roles),
                "parsed_count": len(parsed_roles),
            },
        )

        return parsed_roles


class AccredRoleProvider(RoleProvider):
    """Accred role provider that fetches roles from EPFL Accred API.

    Calls the EPFL Accred authorizations endpoint to fetch user authorizations
    and maps them to CO2 application roles based on:
    - authorization.name starting with "co2."
    - authorization.accredunitid as the unit scope

    This is a placeholder implementation that can be extended to support
    more sophisticated role mapping logic.
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

    async def get_roles(
        self, userinfo: Dict[str, Any], sciper: int
    ) -> List[Dict[str, Any]]:
        """Fetch roles from EPFL Accred API.

        Args:
            userinfo: OAuth userinfo dict (not used in accred provider)
            sciper: EPFL SCIPER number to query authorizations

        Returns:
            List of role dicts derived from authorizations
        """
        if not all([self.api_url, self.api_username, self.api_key]):
            logger.error(
                "Cannot fetch roles: Accred API not configured",
                extra={"sciper": sciper},
            )
            return []

        try:
            # Call EPFL Accred authorizations endpoint
            url = f"{self.api_url}/authorizations"
            params: dict[str, str | int] = {
                "type": "right",
                "persid": sciper,
                "state": "active",
                "expand": "0",
                "searchauthorization": "co2.",
            }

            # example using httpx for async HTTP requests
            # https://api-test.epfl.ch/v1/authorizations?type=right&persid=352707&state=active&expand=0&searchauthorization=co2.
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params,
                    auth=(self.api_username, self.api_key),
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            authorizations = data.get("authorizations", [])

            if not authorizations:
                logger.info(
                    "No authorizations found in Accred API", extra={"sciper": sciper}
                )
                return []

            # Map authorizations to roles
            roles = []
            # "co2.user.std", --> applied to unit
            # "co2.user.principal", --> applied to unit
            # "co2.user.secondary", --> applied to unit
            # "co2.backoffice.admin", --> applied globally
            # "co2.backoffice.std" --> applied to affiliation

            for auth in authorizations:
                auth_name = auth.get("name", "")

                # Only process authorizations starting with "co2."
                if not auth_name.startswith("co2."):
                    continue

                # Check if authorization is active
                if auth.get("state") != "active":
                    continue

                accred_unit_id = auth.get("accredunitid")

                if not accred_unit_id:
                    logger.warning(
                        "Authorization missing accredunitid, skipping",
                        extra={"auth_name": auth_name, "sciper": sciper},
                    )
                    continue
                if auth_name == "co2.backoffice.admin":
                    # Global admin role
                    roles.append({"role": auth_name, "on": "global"})
                elif auth_name == "co2.backoffice.std":
                    affiliations_names = (
                        auth.get("reason").get("resource").get("sortpath")
                    )
                    # Map to affiliation scope (placeholder logic)
                    roles.append(
                        {"role": auth_name, "on": {"affiliation": affiliations_names}}
                    )
                else:
                    # Map authorization to role with unit scope
                    roles.append({"role": auth_name, "on": {"unit": accred_unit_id}})

            logger.info(
                "Fetched roles from Accred API",
                extra={
                    "sciper": sciper,
                    "total_authorizations": len(authorizations),
                    "co2_roles": len(roles),
                },
            )

            return roles

        except httpx.HTTPStatusError as e:
            logger.error(
                "Accred API HTTP error",
                extra={
                    "sciper": sciper,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            return []
        except httpx.RequestError as e:
            logger.error(
                "Accred API request error", extra={"sciper": sciper, "error": str(e)}
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error fetching roles from Accred API",
                extra={"sciper": sciper, "error": str(e), "type": type(e).__name__},
            )
            return []


def get_role_provider() -> RoleProvider:
    """Factory function to get the configured role provider.

    Returns the appropriate role provider based on the
    ROLE_PROVIDER_PLUGIN setting.

    Returns:
        RoleProvider instance

    Raises:
        ValueError: If an unknown provider type is configured
    """
    provider_type = settings.ROLE_PROVIDER_PLUGIN

    if provider_type == "default":
        logger.info("Using DefaultRoleProvider (JWT claims)")
        return DefaultRoleProvider()
    elif provider_type == "accred":
        logger.info("Using AccredRoleProvider (EPFL Accred API)")
        return AccredRoleProvider()
    else:
        logger.error(
            "Unknown role provider type, falling back to default",
            extra={"provider_type": provider_type},
        )
        return DefaultRoleProvider()
