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

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.role_priority import pick_role_for_provider_code
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
        code: str,
        email: str,
        function: Optional[str] = None,
        display_name: Optional[str] = None,
        roles: Optional[List[Role]] = None,
        provider: Optional[str] = None,
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
        if existing_user:
            return await self.user_repo.update(
                id=existing_user.id,
                display_name=display_name,
                roles=roles,
                provider=provider,
                function=function,
            )
        return await self.user_repo.create(
            code=code,
            email=email,
            display_name=display_name,
            roles=roles,
            provider=provider,
            function=function,
        )

    async def unit_sync_from_provider(
        self, provider: str, provider_unit_codes: list[str], current_user: User
    ) -> list[int]:
        """Sync units and their principals from provider."""
        # step 3. Fetch full unit details from provider
        unit_provider = get_unit_provider(provider_type=provider)
        units = await unit_provider.get_units(unit_ids=provider_unit_codes)

        # 4. Upsert units with full metadata
        role_provider = get_role_provider(provider_type=current_user.provider)
        unit_ids = []
        for unit in units:
            if not unit.principal_user_provider_code:
                raise ValueError(f"Unit {unit.id} missing principal_user_provider_code")
            # Upsert principal user recursively
            principal_user = await role_provider.get_user_by_user_id(
                unit.principal_user_provider_code
            )
            # // retriev display name and email from role provider if possible
            if (
                unit.principal_user_provider_code != current_user.code
            ) and principal_user:
                await self.upsert_user(
                    email=principal_user.get("email", ""),
                    code=principal_user.get("code", ""),
                    display_name=principal_user.get("display_name", None),
                    id=None,
                    roles=principal_user.get("roles", []),
                    stop_recursion=True,
                    provider=principal_user.get("provider", None),
                    function=principal_user.get("function", None),
                )
            created_unit = await self.unit_service.upsert(
                unit_data=unit,
                provider=current_user.provider,
            )
            unit_ids.append(created_unit.id)
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
            await self.unit_user_service.upsert(
                unit_id=unit_id,
                user_id=user.id,
                role=chosen_role,
            )

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
        code: str,
        display_name: Optional[str] = None,
        function: Optional[str] = None,
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
        user = await self._upsert_user_identity(
            id, code, email, function, display_name, roles, provider
        )

        if stop_recursion:
            return user

        provider_codes = self.get_user_unit_ids(roles)
        if not provider_codes:
            return user

        if not user.provider:
            raise ValueError("User provider is required for unit synchronization")

        # Pulls units from the provider,
        # upserts missing principal users,
        # then upserts units.”
        unit_ids = await self.unit_sync_from_provider(
            provider=user.provider,
            provider_unit_codes=provider_codes,
            current_user=user,
        )

        # Upserts UnitUser relationships by resolving
        # the user’s role per unit (should be .id to .id mapping and not .code)
        await self.unit_membership_sync_user(
            user=user,
            roles=roles,
            unit_ids=unit_ids,
            unit_codes=provider_codes,
        )

        logger.info(
            "User upserted with units",
            extra={
                "user_id": user.id,
                "unit_count": len(provider_codes),
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
