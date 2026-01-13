"""Role provider plugin system for flexible role management.

This module provides an abstract base class and implementations for fetching
user roles from different sources (JWT claims, EPFL Accred API, etc.).
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import GlobalScope, Role, RoleName, RoleScope

logger = get_logger(__name__)
settings = get_settings()


class RoleProvider(ABC):
    """Abstract base class for role providers.

    Role providers are responsible for fetching and transforming user roles
    from various sources into the standardized hierarchical format:
    [{"role": RoleName.CO2_USER_STD, "on": {"unit": "12345"}}]
    """

    type: str = "abstract"

    @abstractmethod
    async def get_user_by_user_id(self, user_id: str) -> Dict[str, Any]:
        """Get user info from the role provider by user ID.

        Args:
            user_id: User ID of the user
        """
        pass

    @abstractmethod
    def get_user_id(self, userinfo: Dict[str, Any]) -> str:
        """Get user ID for a user.

        Args:
            userinfo: OAuth userinfo dict from the identity provider
        Returns:
            User ID as a string
        """
        pass

    @abstractmethod
    async def get_roles(self, userinfo: Dict[str, Any]) -> List[Role]:
        """Get roles for a user.

        Args:
            userinfo: OAuth userinfo dict from the identity provider

        Returns:
            List of role dicts with structure:
              [{"role": RoleName.CO2_USER_STD, "on": {"unit": "12345"}}]
              or [{"role": RoleName.CO2_BACKOFFICE_ADMIN, "on": GlobalScope()}]
              for global roles
        """
        pass

    @abstractmethod
    async def get_roles_by_user_id(self, user_id: str) -> List[Role]:
        """Get roles for a user by user ID.

        Args:
            user_id: User ID of the user
        Returns:
            List of role dicts with structure:
              [{"role": RoleName.CO2_USER_STD, "on": {"unit": "12345"}}]
              or [{"role": RoleName.CO2_BACKOFFICE_ADMIN, "on": GlobalScope()}]
              for global roles
        """
        pass


class DefaultRoleProvider(RoleProvider):
    """Default role provider that extracts roles from JWT claims.

    Expects roles in flat string format from JWT claims:
    - "co2.user.std@unit:12345" → {"role": "co2.user.std", "on": {"unit": "12345"}}
    - "co2.backoffice.admin@global" → {"role": "co2.backoffice.admin", "on": "global"}

    Roles without scope (bare strings) will be skipped with a warning.
    """

    type: str = "default"

    def get_user_id(self, userinfo: Dict[str, Any]) -> str:
        """Get user ID for a user.

        Args:
            userinfo: OAuth userinfo dict from the identity provider
        Returns:
            User ID as a string
        """
        user_id = userinfo.get("sub")
        if not user_id:
            logger.warning(
                "No user ID found in userinfo",
                extra={"userinfo": userinfo},
            )
            return ""
        return str(user_id)

    async def get_roles(self, userinfo: Dict[str, Any]) -> List[Role]:
        """Extract and parse roles from JWT claims.

        Args:
            userinfo: OAuth userinfo dict containing 'roles' claim

        Returns:
            List of parsed Role objects
        """
        user_id = self.get_user_id(userinfo)
        jwt_roles = userinfo.get("roles", [])

        if not jwt_roles:
            logger.warning(
                "No roles found in JWT claims for user",
                extra={"user_id": user_id, "email": userinfo.get("email")},
            )
            return []

        parsed_roles: List[Role] = []

        for role_str in jwt_roles:
            if not isinstance(role_str, str):
                logger.warning(
                    "Invalid role format (not a string), skipping",
                    extra={"role": role_str, "user_id": user_id},
                )
                continue

            if "@" not in role_str:
                logger.warning(
                    "Role without scope (@), skipping",
                    extra={"role": role_str, "user_id": user_id},
                )
                continue

            # Parse "role@scope:value" format
            parts = role_str.split("@", 1)
            role_name = RoleName(parts[0].strip())
            scope_part = parts[1].strip()

            if scope_part == "global":
                parsed_roles.append(Role(role=role_name, on=GlobalScope()))
            elif ":" in scope_part:
                # Parse "unit:12345" → {"unit": "12345"}
                scope_type, scope_id = scope_part.split(":", 1)
                scope_type = scope_type.strip()
                scope_id = scope_id.strip()
                if scope_type == "unit":
                    parsed_roles.append(
                        Role(
                            role=role_name,
                            on=RoleScope(provider_code=scope_id),
                        )
                    )
                elif scope_type == "affiliation":
                    parsed_roles.append(
                        Role(
                            role=role_name,
                            on=RoleScope(affiliation=scope_id),
                        )
                    )
            else:
                logger.warning(
                    "Invalid scope format, skipping",
                    extra={"role": role_str, "scope": scope_part, "user_id": user_id},
                )
                continue

        logger.info(
            "Parsed roles from JWT claims",
            extra={
                "user_id": user_id,
                "raw_count": len(jwt_roles),
                "parsed_count": len(parsed_roles),
            },
        )

        return parsed_roles

    async def get_roles_by_user_id(self, user_id: str) -> List[Role]:
        """Not implemented for DefaultRoleProvider.

        Args:
            user_id: User ID of the user
        Returns:
            Empty list as this provider does not support fetching by user ID
        """
        logger.warning(
            "get_roles_by_user_id not implemented for DefaultRoleProvider",
            extra={"user_id": user_id},
        )
        return []


class TestRoleProvider(RoleProvider):
    """Test role provider for development and testing."""

    type: str = "test"

    def get_user_id(self, userinfo: Dict[str, Any]) -> str:
        """Get user ID for a user.

        Args:
            userinfo: OAuth userinfo dict from the identity provider
        Returns:
            User ID as a string
        """
        user_id = userinfo.get("requested_role", "co2.user.std")
        return self._make_user_id(f"testuser_{user_id}")

    async def get_roles(self, userinfo: Dict[str, Any]) -> List[Role]:
        """Return test roles for a user.

        Args:
            userinfo: Contains the requested role for the test user

        Returns:
            List of test Role objects
        """
        requested_role = userinfo.get("requested_role", "co2.user.std")
        # Create roles based on requested role
        roles: List[Role] = []
        if requested_role == "co2.user.std":
            roles = [
                Role(
                    role=RoleName.CO2_USER_STD,
                    on=RoleScope(provider_code="12345", affiliation="testaffiliation"),
                )
            ]
        elif requested_role == "co2.user.secondary":
            roles = [
                Role(
                    role=RoleName.CO2_USER_SECONDARY,
                    on=RoleScope(provider_code="12345", affiliation="testaffiliation"),
                )
            ]
        elif requested_role == "co2.user.principal":
            roles = [
                Role(
                    role=RoleName.CO2_USER_PRINCIPAL,
                    on=RoleScope(provider_code="12345", affiliation="testaffiliation"),
                )
            ]
        elif requested_role == "co2.backoffice.std":
            roles = [
                Role(
                    role=RoleName.CO2_BACKOFFICE_STD,
                    on=RoleScope(affiliation="testaffiliation"),
                )
            ]
        elif requested_role == "co2.backoffice.admin":
            roles = [
                Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope(scope="global"))
            ]
        elif requested_role == "co2.service.mgr":
            roles = [
                Role(role=RoleName.CO2_SERVICE_MGR, on=GlobalScope(scope="global"))
            ]
        else:
            roles = []

        return roles

    async def get_user_by_user_id(self, user_id: str) -> Dict[str, Any]:
        """Return test user info by user ID.

        Args:
            user_id: User ID of the user
        Returns:
            User info dict for the test user
        """
        roles = await self.get_roles_by_user_id(user_id)
        user_insert = {
            "code": user_id,
            "provider": self.type,
            "email": f"{user_id}@testprovider.local",
            "display_name": f"Test User {user_id}",
            "function": "Tester",
            "roles": roles,
        }
        return user_insert

    async def get_roles_by_user_id(self, user_id: str) -> List[Role]:
        """Return test roles for a user by their user ID.

        Args:
            user_id: User ID of the user
        Returns:
            List of test Role objects
        """
        # From user_id, find the requested role
        for role_name in RoleName.__members__.values():
            # Make a consistent 10-digit user ID based on user_id
            role_user_id = self._make_user_id(f"testuser_{role_name.value}")
            if user_id == role_user_id:
                userinfo = {"requested_role": role_name.value}
                return await self.get_roles(userinfo)
        # No matching test user found
        return []

    def _make_user_id(self, user_id: str) -> str:
        """Make a consistent 10-digit user ID based on user_id."""
        return str(int(hashlib.sha256(user_id.encode()).hexdigest(), 16))[:10]


class AccredRoleProvider(RoleProvider):
    """Accred role provider that fetches roles from EPFL Accred API.

    Calls the EPFL Accred authorizations endpoint to fetch user authorizations
    and maps them to CO2 application roles based on:
    - authorization.name starting with "co2."
    - authorization.accredunitid as the unit scope

    This is a placeholder implementation that can be extended to support
    more sophisticated role mapping logic.
    """

    type: str = "accred"

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

    def get_user_id(self, userinfo: Dict[str, Any]) -> str:
        """Get user ID for a user.

        Args:
            userinfo: OAuth userinfo dict from the identity provider
        Returns:
            User ID as a string
        """
        # TODO: rename user_id is provider_code or persid/sciper in Accred
        user_id = userinfo.get("uniqueid")  # return user_id as str
        if not user_id:
            logger.warning(
                "No user ID found in userinfo",
                extra={"userinfo": userinfo},
            )
            raise ValueError("User ID is required for Accred role provider")
        return str(user_id)

    async def get_roles(self, userinfo: Dict[str, Any]) -> List[Role]:
        """Fetch roles from EPFL Accred API.

        Args:
            userinfo: OAuth userinfo dict (not used in accred provider)
            user_id: User ID to query authorizations

        Returns:
            List of role dicts derived from authorizations
        """
        try:
            user_id = self.get_user_id(userinfo)
            return await self.get_roles_by_user_id(user_id)
        except ValueError as e:
            logger.error(f"Error getting roles: {e}", extra={"userinfo": userinfo})
            return []

    async def get_user_by_user_id(self, user_id: str) -> Dict[str, Any]:
        """Fetch user info from EPFL Accred API.

        Args:
            user_id: User ID to query
        Returns:
            User info dict from Accred API
        """
        if not all([self.api_url, self.api_username, self.api_key]):
            logger.error(
                "Cannot fetch user: Accred API not configured",
                extra={"user_id": user_id},
            )
            return {}

        try:
            # Call EPFL Accred user endpoint
            # /v1/accreds?persid=352707&onlymainaccred=true
            # /v1/persons/101116
            url = f"{self.api_url}/persons/{user_id}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    auth=(self.api_username, self.api_key),
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            position = data.get("position", {})
            if not position:
                logger.info(
                    "No position found in Accred API", extra={"user_id": user_id}
                )
                return {}
            logger.info(
                "Fetched user from Accred API",
                extra={"user_id": user_id},
            )
            user_insert = {
                "code": str(data.get("id")),  # provider user id
                "provider": self.type,
                "email": data.get("email"),
                "display_name": data.get("display"),
                "function": position.get("labelen"),
            }

            roles = await self.get_roles_by_user_id(user_id)

            user_insert["roles"] = roles
            return user_insert

        except httpx.HTTPStatusError as e:
            logger.error(
                "Accred API HTTP error",
                extra={
                    "user_id": user_id,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "Accred API request error", extra={"user_id": user_id, "error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error fetching user from Accred API",
                extra={"user_id": user_id, "error": str(e), "type": type(e).__name__},
            )
            logger.exception("Unexpected error fetching user from Accred API")
            raise

    async def get_roles_by_user_id(self, user_id: str) -> List[Role]:
        """Fetch roles from EPFL Accred API.

        Args:
            user_id: User ID to query authorizations
        Returns:
            List of role dicts derived from authorizations
        """

        if not all([self.api_url, self.api_username, self.api_key]):
            logger.error(
                "Cannot fetch roles: Accred API not configured",
                extra={"user_id": user_id},
            )
            return []

        try:
            # Call EPFL Accred authorizations endpoint
            url = f"{self.api_url}/authorizations"
            params: dict[str, str | int] = {
                "type": "right",
                "persid": user_id,
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
                    "No authorizations found in Accred API", extra={"user_id": user_id}
                )
                return []

            # Map authorizations to roles
            roles: List[Role] = []
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
                        extra={"auth_name": auth_name, "user_id": user_id},
                    )
                    continue
                if auth_name == RoleName.CO2_BACKOFFICE_ADMIN:
                    # Global admin role
                    roles.append(Role(role=auth_name, on=GlobalScope()))
                elif auth_name == RoleName.CO2_BACKOFFICE_STD:
                    affiliations_names = (
                        auth.get("reason").get("resource").get("sortpath")
                    )
                    # Map to affiliation scope (placeholder logic)
                    roles.append(
                        Role(
                            role=auth_name,
                            on=RoleScope(affiliation=affiliations_names),
                        )
                    )
                else:
                    # Map authorization to role with unit scope
                    roles.append(
                        Role(
                            role=auth_name,
                            on=RoleScope(provider_code=str(accred_unit_id)),
                        )
                    )

            logger.info(
                "Fetched roles from Accred API",
                extra={
                    "user_id": user_id,
                    "total_authorizations": len(authorizations),
                    "co2_roles": len(roles),
                },
            )

            return roles

        except httpx.HTTPStatusError as e:
            logger.error(
                "Accred API HTTP error",
                extra={
                    "user_id": user_id,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "Accred API request error", extra={"user_id": user_id, "error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error fetching roles from Accred API",
                extra={"user_id": user_id, "error": str(e), "type": type(e).__name__},
            )
            logger.exception("Unexpected error fetching roles from Accred API")
            raise


def get_role_provider(provider_type: str | None = None) -> RoleProvider:
    """Factory function to get the configured role provider.

    Returns the appropriate role provider based on the
    PROVIDER_PLUGIN setting.

    Args:
        provider_type: Optional provider type override

    Returns:
        RoleProvider instance

    Raises:
        ValueError: If an unknown provider type is configured
    """
    if not provider_type:
        provider_type = settings.PROVIDER_PLUGIN

    if provider_type == "default":
        logger.info("Using DefaultRoleProvider (JWT claims)")
        return DefaultRoleProvider()
    elif provider_type == "accred":
        logger.info("Using AccredRoleProvider (EPFL Accred API)")
        return AccredRoleProvider()
    elif provider_type == "test":
        logger.info("Using TestRoleProvider (for testing)")
        return TestRoleProvider()
    else:
        logger.error(
            "Unknown role provider type, falling back to default",
            extra={"provider_type": provider_type},
        )
        return DefaultRoleProvider()
