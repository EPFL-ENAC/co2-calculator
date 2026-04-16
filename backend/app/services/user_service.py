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
from app.core.role_priority import pick_role_for_institutional_id
from app.models.unit import Unit
from app.models.user import Role, RoleScope, User, UserProvider
from app.repositories.user_repo import UpsertUserResult, UserRepository
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

    def get_uniq_unit_institutional_id_from_roles(
        self, roles: Optional[List[Role]]
    ) -> list[str]:
        """Get list of unit IDs associated with a user (from RoleScope.unit for now).
        here unit ids should be unit institutional ids. a.k.a CF
        """
        if not roles:
            return []

        unit_institutional_ids: set[str] = set()
        for role in roles:
            if isinstance(role.on, RoleScope) and role.on.institutional_id:
                unit_institutional_ids.add(role.on.institutional_id)

        return list(unit_institutional_ids)

    async def _upsert_user_identity(
        self,
        id: Optional[int],
        institutional_id: str,
        email: str,
        function: Optional[str] = None,
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[UserProvider] = None,
    ) -> User:
        """Upsert user identity scoped by (institutional_id, provider).

        User lookup is performed by institutional_id scoped to provider to prevent
        cross-provider collisions. Email lookup is only used as fallback for updates
        where the user already exists with matching provider.
        """
        if provider is None:
            raise ValueError("Provider is required for user upsert")

        # Primary lookup: scoped by (institutional_id, provider)
        existing_user = await self.user_repo.get_by_institutional_id_and_provider(
            institutional_id=institutional_id,
            provider=provider,
        )

        # Fallback for updates: if ID not found and we have an ID, try by PK
        if not existing_user and id:
            existing_user = await self.user_repo.get_by_id(id)
            # Validate provider match if found by PK
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

        # Secondary fallback: email lookup (only for same provider)
        if not existing_user:
            existing_user = await self.user_repo.get_by_email(email)
            # Only use email match if provider aligns
            if existing_user and existing_user.provider != provider:
                existing_user = None

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
                institutional_id=institutional_id,
                email=email,
                display_name=display_name,
                roles=roles,
                provider=provider,
                function=function,
            )
        await self.session.flush()
        return user

    async def unit_membership_sync_user(
        self,
        user: User,
        roles: List[Role],
        units: List[Unit],
    ) -> None:
        """Sync UnitUser associations for a user based on their current roles.

        Strategy: delete all existing associations, then recreate from current roles.
        This handles role changes, unit remapping, and removed associations cleanly.
        """
        if user is None or user.id is None:
            raise ValueError("User must have a valid ID for unit membership sync")

        # 1. Delete all existing associations for this user
        await self.unit_user_service.delete_all_for_user(user.id)

        # 2. Recreate associations from current roles
        created_count = 0
        for unit in units:
            if unit.institutional_id is None:
                raise ValueError(
                    "unit.institutional_id should exist before picking a role"
                )
            chosen_role = pick_role_for_institutional_id(roles, unit.institutional_id)
            if not chosen_role:
                logger.warning(
                    "No valid role found for user-unit association",
                    extra={
                        "user_id": sanitize(user.id),
                        "unit_id": sanitize(unit.id),
                        "unit_institutional_id": sanitize(unit.institutional_id),
                    },
                )
                continue
            if unit.id is None:
                raise ValueError(
                    "unit.id should exist before trying to create N-N relationship"
                )
            await self.unit_user_service.upsert(
                unit_id=unit.id,
                user_id=user.id,
                role=chosen_role,
            )
            created_count += 1

        await self.session.flush()

        logger.info(
            "User unit memberships synced",
            extra={
                "user_id": sanitize(user.id),
                "unit_count": created_count,
                "provider": user.provider,
            },
        )

    async def upsert_user(
        self,
        id: Optional[int],
        email: str,
        institutional_id: str,
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
            id, institutional_id, email, function, display_name, roles, provider
        )

        if stop_recursion:
            return user

        unit_institutional_ids: list[str] = (
            self.get_uniq_unit_institutional_id_from_roles(roles)
        )
        if not unit_institutional_ids:
            # No unit-scoped roles — clean up any existing associations
            if user.id is not None:
                await self.unit_user_service.delete_all_for_user(user.id)
            return user

        if user.provider is None:
            raise ValueError("User provider is required for unit synchronization")

        # we used to sync units on user upsert, but not anymore
        if roles is None:
            roles = []

        # 1. Resolve unit.ids from the database based on unit_institutional_ids
        units = await self.unit_service.get_by_institutional_ids(unit_institutional_ids)

        if not units:
            logger.warning(
                "No units found in DB for the given institutional IDs",
                extra={
                    "user_id": sanitize(user.id),
                    "unit_institutional_ids": sanitize(unit_institutional_ids),
                },
            )
            if user.id is None:
                raise ValueError("User ID is required for unit synchronization")
            # Still delete stale associations even if no units matched
            await self.unit_user_service.delete_all_for_user(user.id)
            return user

        # 2 & 3. Delete old associations and recreate from current roles
        await self.unit_membership_sync_user(
            user=user,
            roles=roles,
            units=units,
        )

        logger.info(
            "User upserted with units",
            extra={
                "id": user.id,
                "unit_count": len(unit_institutional_ids),
                "provider": user.provider,
            },
        )

        return user

    async def bulk_create(
        self,
        users: List[User],
    ) -> UpsertUserResult:
        """Bulk create users."""
        logger.info(f"Bulk creating/updating {len(users)} users")
        db_objs = await self.user_repo.bulk_upsert(users)
        await self.session.flush()  # Ensure user IDs are populated
        return db_objs

    async def bulk_upsert(self, users: List[User]) -> UpsertUserResult:
        """Upsert users — business logic goes here if needed
        (validation, enrichment, etc.)"""
        db_objs = await self.user_repo.bulk_upsert(users)
        await self.session.flush()  # Ensure user IDs are populated
        return db_objs

    async def get_by_id(self, id: int) -> Optional[User]:
        """Get user by id."""
        return await self.user_repo.get_by_id(id)

    async def get_by_code(self, code: str) -> Optional[User]:
        """Get user by code (deprecated: use get_by_institutional_id_and_provider)."""
        return await self.user_repo.get_by_code(code)

    async def get_by_institutional_id_and_provider(
        self,
        institutional_id: str,
        provider: UserProvider,
    ) -> Optional[User]:
        """Get user by institutional_id scoped to provider.

        This is the primary user resolution method for authentication.
        """
        return await self.user_repo.get_by_institutional_id_and_provider(
            institutional_id=institutional_id,
            provider=provider,
        )

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
            institutional_id=str(user_data.get("id")),
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
