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

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.core.role_priority import pick_role_for_unit
from app.models.user import Role, RoleScope, User
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.repositories.unit_repo import UnitRepository
from app.repositories.unit_user_repo import UnitUserRepository
from app.repositories.user_repo import UserRepository
from app.services.unit_user_service import UnitUserService

logger = get_logger(__name__)


class UserService:
    """Service for user business logic and orchestration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.unit_repo = UnitRepository(session)
        self.unit_user_repo = UnitUserRepository(session)
        self.unit_user_service = UnitUserService(session)

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
    ) -> User:
        """
        Create or update a user with all related entities.

        This orchestrates:
        1. User creation/update
        2. Unit synchronization from provider
        3. UnitUser association management
        """
        # step 1. Get or create user
        existing_user = await self.user_repo.get_by_email(email)

        if existing_user:
            user = await self.user_repo.update(
                user_id=existing_user.id, display_name=display_name, roles=roles
            )
        else:
            user = await self.user_repo.create(
                email=email, display_name=display_name, user_id=user_id, roles=roles
            )

        if stop_recursion:
            return user
        # step 2. Extract unit IDs from roles
        unit_ids = self.get_user_unit_ids(roles)

        if not unit_ids:
            return user

        # step 3. Fetch full unit details from provider
        unit_provider = get_unit_provider()
        units = await unit_provider.get_units(unit_ids=unit_ids)

        # 4. Upsert units with full metadata
        role_provider = get_role_provider()
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
                )
            await self.unit_repo.upsert(unit, user_id=user.id)

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
            },
        )

        return user

    async def get_by_id(self, user_id: str) -> User:
        """Get user by ID."""
        return await self.user_repo.get_by_id(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self.user_repo.get_by_email(email)

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count users with optional filters."""
        return await self.user_repo.count(filters)
