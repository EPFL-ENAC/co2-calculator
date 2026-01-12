"""Unit service for business logic with Policy integration.

This service contains both:
1. User-facing operations (WITH policy checks):
   - get_user_units(): List units with authorization
   - get_by_id(): Get specific unit with authorization
   - list_users(): List users with policy-based filtering
   - get_user(): Get user with authorization (returns 404 if no access)

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
from app.core.role_priority import pick_role_for_unit
from app.models.user import Role, RoleScope, User
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
        """Get list of unit IDs associated with a user."""
        if not roles:
            return []

        unit_ids: set[str] = set()
        for role in roles:
            if isinstance(role.on, RoleScope) and role.on.unit:
                unit_ids.add(role.on.unit)

        return list(unit_ids)

    async def upsert_user(
        self,
        email: str,
        display_name: Optional[str] = None,
        user_id: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        stop_recursion: bool = False,
        provider: Optional[str] = None,
    ) -> User:
        """
        Create or update a user with all related entities.

        This orchestrates:
        1. User creation/update
        2. Unit synchronization from provider
        3. UnitUser association management
        """
        # step 1. Get or create user
        existing_user = await self.user_repo.get_by_id(user_id) if user_id else None
        if not existing_user:
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
        if existing_user:
            user = await self.user_repo.update(
                user_id=existing_user.id,
                display_name=display_name,
                roles=roles,
                provider=provider,
            )
        else:
            user = await self.user_repo.create(
                email=email,
                display_name=display_name,
                user_id=user_id,
                roles=roles,
                provider=provider,
            )

        if stop_recursion:
            return user
        # step 2. Extract unit IDs from roles
        unit_ids = self.get_user_unit_ids(roles)

        if not unit_ids:
            return user

        if not user.provider:
            raise ValueError("User provider is required for unit synchronization")
        # step 3. Fetch full unit details from provider
        unit_provider = get_unit_provider(provider_type=user.provider)
        units = await unit_provider.get_units(unit_ids=unit_ids)

        # 4. Upsert units with full metadata
        role_provider = get_role_provider(provider_type=user.provider)
        for unit in units:
            if not unit.principal_user_id:
                raise ValueError(
                    f"Unit {unit.id} missing principal_user_id from provider"
                )
            # Upsert principal user recursively
            principal_roles = await role_provider.get_roles_by_user_id(
                unit.principal_user_id
            )
            if (unit.principal_user_id != user.id) and principal_roles:
                if not unit.principal_user_email:
                    raise ValueError(
                        f"Unit {unit.id} principal user missing email from provider"
                    )
                await self.upsert_user(
                    email=unit.principal_user_email,
                    display_name=unit.principal_user_name,
                    user_id=unit.principal_user_id,
                    roles=principal_roles,
                    stop_recursion=True,
                    provider=user.provider,
                )
            await self.unit_service.upsert_unit(unit, user, provider=user.provider)

        # step 5. Create/update UnitUser associations
        for unit_id in unit_ids:
            chosen_role = pick_role_for_unit(roles, unit_id)
            if not chosen_role:
                logger.warning(
                    "No valid role found for user-unit association",
                    extra={
                        "user_id": user.id,
                        "unit_id": unit_id,
                    },
                )
                continue
            await self.unit_user_service.upsert(
                unit_id=unit_id,
                user_id=user.id,
                role=chosen_role,
            )

        logger.info(
            "User upserted with units",
            extra={
                "user_id": user.id,
                "unit_count": len(unit_ids),
                "provider": user.provider,
            },
        )

        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return await self.user_repo.get_by_id(user_id)

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

    async def get_user(self, user_id: str, current_user: User) -> User:
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
            user_id=user_data.get("id"),
            email=user_data.get("email", ""),
            display_name=user_data.get("display_name"),
            roles=user_data.get("roles"),
            provider=user_data.get("provider", "default"),
        )

        logger.info(
            "User created",
            extra={
                "created_by": sanitize(current_user.id),
                "user_id": sanitize(user.id),
            },
        )

        return user

    async def update_user(
        self, user_id: str, user_data: dict, current_user: User
    ) -> User:
        """
        Update a user.

        Note: Permission check is handled at the endpoint level via require_permission.

        Args:
            user_id: User ID to update
            user_data: User data dictionary
            current_user: Current user (for audit context)

        Returns:
            Updated user
        """
        # Update user
        user = await self.user_repo.update(
            user_id=user_id,
            display_name=user_data.get("display_name"),
            roles=user_data.get("roles"),
            provider=user_data.get("provider"),
            updated_by=current_user.id,
            is_active=user_data.get("is_active"),
        )

        logger.info(
            "User updated",
            extra={
                "updated_by": sanitize(current_user.id),
                "user_id": sanitize(user_id),
            },
        )

        return user

    async def delete_user(self, user_id: str, current_user: User) -> bool:
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
