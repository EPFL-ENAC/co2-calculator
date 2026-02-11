"""Unit service for business logic with Policy integration.

This service contains both:
1. User-facing operations (WITH policy checks):
   - get_user_units(): List units with authorization
   - get_by_id(): Get specific unit with authorization

2. Internal operations (NO policy checks):
   - upsert_unit(): System sync from OAuth/providers

Policy authorization is only applied to user-initiated API requests,
not internal system operations like OAuth callbacks or provider synchronization.
"""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy
from app.core.role_priority import pick_role_for_provider_code
from app.models.unit import Unit
from app.models.user import Role, RoleScope, User, UserProvider
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.repositories.user_repo import UserRepository
from app.services.unit_service import UnitService
from app.services.unit_user_service import UnitUserService

logger = get_logger(__name__)


class UserService:
    """Service for user business logic and orchestration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.unit_user_service = UnitUserService(session)
        self.unit_service = UnitService(session)

    def get_user_unit_ids(self, roles: Optional[List[Role]]) -> list[str]:
        """Get list of unit IDs associated with a user (from RoleScope.unit for now)."""
        if not roles:
            return []

        unit_ids: set[str] = set()
        for role in roles:
            if isinstance(role.on, RoleScope) and role.on.provider_code:
                unit_ids.add(role.on.provider_code)

        return list(unit_ids)

    async def _upsert_user_identity(
        self,
        id: Optional[int],
        provider_code: str,
        email: str,
        function: Optional[str] = None,
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[UserProvider] = None,
    ) -> User:
        existing_user = await self.user_repo.get_by_id(id) if id else None
        if not existing_user:
            # fallback to email lookup
            existing_user = await self.user_repo.get_by_email(email)
        if existing_user and existing_user.provider != provider:
            logger.warning(
                "User provider mismatch during upsert",
                extra={
                    "user_id": existing_user.id,
                    "existing_provider": existing_user.provider,
                    "new_provider": provider,
                },
            )
            raise ValueError("User provider mismatch during upsert")
        if existing_user and existing_user.id is not None:
            user = await self.user_repo.update(
                id=existing_user.id,
                display_name=display_name,
                roles=roles,
                provider=provider,
                function=function,
            )
        else:
            user = await self.user_repo.create(
                provider_code=provider_code,
                email=email,
                display_name=display_name,
                roles=roles,
                provider=provider,
                function=function,
            )
        await self.session.flush()
        return user

    async def unit_sync_from_provider(
        self,
        provider: UserProvider,
        provider_unit_codes: list[str],
        skip_principal_user_for_provider_code: Optional[str] = None,
    ) -> list[int]:
        """
        Sync units and their principals from provider.

        Args:
            provider: The user provider type (e.g., UserProvider.ACCRED)
            provider_unit_codes: List of unit codes to sync
            skip_principal_user_for_provider_code: Optional - skip upserting the principal user
                                                 if it matches this provider_code.
                                                 Used to avoid upserting the current user.
        """
        # Fetch full unit details from provider
        unit_provider = get_unit_provider(provider_type=provider)
        units = await unit_provider.get_units(unit_ids=provider_unit_codes)

        # Upsert units with full metadata
        role_provider = get_role_provider(provider_type=provider)
        unit_ids = []
        for unit in units:
            if not unit.principal_user_provider_code:
                raise ValueError(f"Unit {unit.id} missing principal_user_provider_code")

            # Upsert principal user if needed
            principal_user = await role_provider.get_user_by_user_id(
                unit.principal_user_provider_code
            )

            # Skip upserting if it's the same as skip_principal_user_for_provider_code
            if (
                principal_user
                and unit.principal_user_provider_code
                != skip_principal_user_for_provider_code
            ):
                await self.upsert_user(
                    email=principal_user.get("email", ""),
                    provider_code=principal_user.get("provider_code", ""),
                    display_name=principal_user.get("display_name", None),
                    id=None,
                    roles=principal_user.get("roles", []),
                    stop_recursion=True,
                    provider=principal_user.get("provider", None),
                    function=principal_user.get("function", None),
                )

            created_unit: Unit = await self.unit_service.upsert(
                unit_data=unit,
            )
            if created_unit is None or created_unit.id is None:
                raise ValueError(f"Failed to upsert unit {unit.id}")
            unit_ids.append(created_unit.id)

        # Flush all unit operations together
        await self.session.flush()

        return unit_ids

    async def unit_membership_sync_user(
        self,
        user: User,
        roles: List[Role],
        unit_ids: List[int],
        unit_codes: List[str],
    ) -> None:
        # step 5. Create/update UnitUser associations
        if len(unit_codes) != len(unit_ids):
            raise ValueError(
                "Unit codes and IDs length mismatch during membership sync"
            )
        for unit_id, unit_code in zip(unit_ids, unit_codes):
            chosen_role = pick_role_for_provider_code(roles, unit_code)
            if not chosen_role:
                logger.warning(
                    "No valid role found for user-unit association",
                    extra={
                        "user_id": sanitize(user.id),
                        "unit_id": sanitize(unit_id),
                    },
                )
                continue
            if user is None or user.id is None:
                raise ValueError("User must have a valid ID for unit membership sync")
            await self.unit_user_service.upsert(
                unit_id=unit_id,
                user_id=user.id,
                role=chosen_role,
            )

        # Flush all unit_user operations together
        await self.session.flush()

        logger.info(
            "User upserted with units",
            extra={
                "user_id": sanitize(user.id),
                "unit_count": len(unit_ids),
                "provider": user.provider,
            },
        )

    async def upsert_user(
        self,
        id: Optional[int],
        email: str,
        provider_code: str,
        display_name: Optional[str] = None,
        function: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        stop_recursion: bool = False,
        provider: Optional[UserProvider] = None,
    ) -> User:
        """
        Create or update a user with all related entities.

        This orchestrates:
        1. User creation/update
        2. Unit synchronization from provider
        3. UnitUser association management
        """
        user = await self._upsert_user_identity(
            id, provider_code, email, function, display_name, roles, provider
        )

        if stop_recursion:
            return user

        provider_unit_codes = self.get_user_unit_ids(roles)
        if not provider_unit_codes:
            return user

        if user.provider is None:
            raise ValueError("User provider is required for unit synchronization")

        # Pulls units from the provider,
        # upserts missing principal users,
        # then upserts units.”
        unit_ids = await self.unit_sync_from_provider(
            provider=user.provider,
            provider_unit_codes=provider_unit_codes,
            skip_principal_user_for_provider_code=user.provider_code,
        )

        if roles is None:
            roles = []
        # Upserts UnitUser relationships by resolving
        # the user’s role per unit (should be .id to .id mapping and not .provider_code)
        await self.unit_membership_sync_user(
            user=user,
            roles=roles,
            unit_ids=unit_ids,
            unit_codes=provider_unit_codes,
        )

        logger.info(
            "User upserted with units",
            extra={
                "id": user.id,
                "unit_count": len(provider_unit_codes),
                "provider": user.provider,
            },
        )

        return user

    async def get_by_id(self, id: int) -> Optional[User]:
        """Get user by id."""
        return await self.user_repo.get_by_id(id)

    async def get_by_code(self, code: str) -> Optional[User]:
        """Get user by code."""
        return await self.user_repo.get_by_code(code)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self.user_repo.get_by_email(email)

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count users with optional filters."""
        return await self.user_repo.count(filters)

    def _build_policy_input(self, user: User, action: str) -> dict:
        """
        Build policy input data from user context.

        Args:
            user: Current user
            action: Action to authorize (read, create, update, delete)

        Returns:
            Policy input dictionary
        """
        input_data = {
            "action": action,
            "resource_type": "user",
            "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
        }

        return input_data

    async def list_users(
        self, user: User, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """
        List users with policy-based filtering.

        This method:
        1. Builds policy input with user context
        2. Queries policy for authorization decision
        3. Applies filters from policy decision
        4. Queries database with filters

        Args:
            user: Current user (for authorization context)
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of authorized users
        """
        # Build policy input
        input_data = self._build_policy_input(user, "read")

        # Query policy for authorization decision
        decision = await query_policy("authz/data/list", input_data)
        logger.info(
            "Policy decision requested for user list",
            extra={
                "user_id": sanitize(user.id),
                "action": "list_users",
                "decision": sanitize(decision),
            },
        )

        if not decision.get("allow", False):
            reason = decision.get("reason", "Access denied")
            logger.warning(
                "Policy denied user list",
                extra={"user_id": sanitize(user.id), "reason": reason},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {reason}",
            )

        # Extract filters from policy decision
        filters = decision.get("filters", {})

        # Remove scope from filters (it's metadata, not a DB field)
        db_filters = {k: v for k, v in filters.items() if k != "scope"}

        # Handle unit_ids filter (if present, filter users by their unit associations)
        if "unit_ids" in filters:
            # For now, we'll need to filter by roles that contain these unit_ids
            # This is a simplified approach - in a real system, you might need
            # to join with unit_user table or use a more complex query
            # For now, we'll return all users and let the policy handle it
            # In practice, you'd want to filter at the DB level
            pass

        # Query database with filters
        users = await self.user_repo.list(skip=skip, limit=limit, filters=db_filters)

        return users

    async def get_user(self, user_id: int, current_user: User) -> User:
        """
        Get a user by ID with authorization.

        Returns 404 (not 403) if user lacks access to hide existence of the user.

        Args:
            user_id: User ID to retrieve
            current_user: Current user (for authorization context)

        Returns:
            User if authorized

        Raises:
            HTTPException: 404 if user not found or access denied
        """
        # Get user
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Build policy input with user context
        input_data = self._build_policy_input(current_user, "read")
        input_data["target_user"] = {
            "id": user.id,
            "email": user.email,
            "roles": user.roles or [],
        }

        # Query policy for authorization
        decision = await query_policy("authz/data/access", input_data)
        logger.info(
            "Policy decision requested for user access",
            extra={
                "user_id": sanitize(current_user.id),
                "target_user_id": sanitize(user_id),
                "decision": sanitize(decision),
            },
        )

        if not decision.get("allow", False):
            # Return 404 to hide existence of user
            logger.warning(
                "Policy denied user access - returning 404",
                extra={
                    "user_id": sanitize(current_user.id),
                    "target_user_id": sanitize(user_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return user

    async def create_user(self, user_data: dict, current_user: User) -> User:
        """
        Create a new user.

        Note: Permission check is handled at the endpoint level via require_permission.

        Args:
            user_data: User data dictionary
            current_user: Current user (for audit context)

        Returns:
            Created user
        """
        # Create user
        user = await self.user_repo.create(
            provider_code=str(user_data.get("id")),
            email=user_data.get("email", ""),
            display_name=user_data.get("display_name"),
            roles=user_data.get("roles"),
            provider=user_data.get("provider", UserProvider.DEFAULT),
        )
        await self.session.flush()

        logger.info(
            "User created",
            extra={
                "created_by": sanitize(current_user.id),
                "user_id": sanitize(user.id),
            },
        )

        return user

    async def update_user(self, id: int, user_data: dict, current_user: User) -> User:
        """
        Update a user.

        Note: Permission check is handled at the endpoint level via require_permission.

        Args:
            id: User ID to update
            user_data: User data dictionary
            current_user: Current user (for audit context)

        Returns:
            Updated user
        """
        # Update user
        user = await self.user_repo.update(
            id=id,
            display_name=user_data.get("display_name"),
            roles=user_data.get("roles"),
            provider=user_data.get("provider"),
        )
        await self.session.flush()

        logger.info(
            "User updated",
            extra={
                "updated_by": sanitize(current_user.id),
                "user_id": sanitize(id),
            },
        )

        return user

    async def delete_user(self, user_id: int, current_user: User) -> bool:
        """
        Delete a user.

        Note: Permission check is handled at the endpoint level via require_permission.

        Args:
            user_id: User ID to delete
            current_user: Current user (for audit context)

        Returns:
            True if deleted, False if not found
        """
        # Delete user
        deleted = await self.user_repo.delete(user_id)

        if deleted:
            await self.session.flush()

            logger.info(
                "User deleted",
                extra={
                    "deleted_by": sanitize(current_user.id),
                    "user_id": sanitize(user_id),
                },
            )

        return deleted

    async def export_users(self, current_user: User) -> List[User]:
        """
        Export all users (with policy-based filtering).

        Args:
            current_user: Current user (for authorization context)

        Returns:
            List of authorized users
        """
        # Use list_users with a high limit to get all users
        return await self.list_users(current_user, skip=0, limit=10000)
