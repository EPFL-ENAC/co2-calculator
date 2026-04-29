"""Role synchronization service for background role updates."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.core.role_priority import pick_role_for_institutional_id
from app.models.user import Role
from app.repositories.user_repo import UserRepository
from app.services.unit_service import UnitService
from app.services.unit_user_service import UnitUserService

logger = get_logger(__name__)


class RoleSyncResult(BaseModel):
    """Result of a role synchronization operation."""

    user_id: int
    has_changed: bool = False
    roles_changed: bool = False
    units_changed: bool = False
    skipped_due_to_ttl: bool = False
    old_roles: List[Role] = []
    new_roles: List[Role] = []


class RoleSyncService:
    """Service for background role synchronization."""

    def __init__(
        self,
        session: AsyncSession,
        sync_ttl_minutes: int = 15,
    ):
        self.session = session
        self.user_repo = UserRepository(session)
        self.unit_user_service = UnitUserService(session)
        self.unit_service = UnitService(session)
        self.sync_ttl = timedelta(minutes=sync_ttl_minutes)

    async def sync_user_roles(
        self,
        user_id: int,
        provider_user: Dict[str, Any],
        force: bool = False,
    ) -> RoleSyncResult:
        """
        Sync user roles from provider.

        Args:
            user_id: User ID to sync
            provider_user: User data from role provider
            force: Force sync even if recently synced

        Returns:
            RoleSyncResult with change details
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("User not found for role sync", extra={"user_id": user_id})
            return RoleSyncResult(user_id=user_id)

        # Check TTL
        if not force and user.last_roles_sync_at:
            time_since_sync = datetime.utcnow() - user.last_roles_sync_at
            if time_since_sync < self.sync_ttl:
                logger.debug(
                    "Skipping role sync - recently synced",
                    extra={
                        "user_id": user_id,
                        "time_since_sync": str(time_since_sync),
                    },
                )
                return RoleSyncResult(
                    user_id=user_id,
                    skipped_due_to_ttl=True,
                )

        # Compare roles
        old_roles = user.roles or []
        new_roles = provider_user.get("roles", [])

        # Convert to comparable format
        def extract_role_key(role):
            role_name = role.role if isinstance(role.role, str) else role.role.value
            if hasattr(role.on, "institutional_id"):
                unit_id = role.on.institutional_id
            elif isinstance(role.on, dict):
                unit_id = role.on.get("institutional_id")
            else:
                unit_id = None
            return (role_name, unit_id)

        old_roles_comparable = sorted(extract_role_key(r) for r in old_roles)
        new_roles_comparable = sorted(extract_role_key(r) for r in new_roles)

        roles_changed = old_roles_comparable != new_roles_comparable

        if not roles_changed:
            logger.debug(
                "No role changes detected",
                extra={"user_id": user_id},
            )
            # Still update timestamp
            user.last_roles_sync_at = datetime.utcnow()
            await self.session.commit()
            return RoleSyncResult(
                user_id=user_id,
                has_changed=False,
                old_roles=old_roles,
                new_roles=new_roles,
            )

        # Update user roles
        user.roles = new_roles
        user.last_roles_sync_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)

        logger.info(
            "User roles updated",
            extra={
                "user_id": user_id,
                "old_roles_count": len(old_roles),
                "new_roles_count": len(new_roles),
            },
        )

        return RoleSyncResult(
            user_id=user_id,
            has_changed=True,
            roles_changed=True,
            old_roles=old_roles,
            new_roles=new_roles,
        )

    async def sync_user_units(
        self,
        user_id: int,
        roles: List[Role],
    ) -> bool:
        """
        Sync user unit associations based on roles.

        Args:
            user_id: User ID to sync
            roles: User roles (may contain unit scopes)

        Returns:
            True if units changed
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.id is None:
            return False

        # Extract unit IDs from roles
        unit_institutional_ids = set()
        for role in roles:
            if hasattr(role, "on") and hasattr(role.on, "institutional_id"):
                if role.on.institutional_id:
                    unit_institutional_ids.add(role.on.institutional_id)

        if not unit_institutional_ids:
            # No unit roles - delete all associations
            await self.unit_user_service.delete_all_for_user(user.id)
            return True

        # Resolve unit IDs from database
        units = await self.unit_service.get_by_institutional_ids(
            list(unit_institutional_ids)
        )

        if not units:
            logger.warning(
                "No units found for role sync",
                extra={
                    "user_id": user_id,
                    "unit_institutional_ids": list(unit_institutional_ids),
                },
            )
            await self.unit_user_service.delete_all_for_user(user.id)
            return True

        # Delete old associations
        await self.unit_user_service.delete_all_for_user(user.id)

        # Create new associations
        for unit in units:
            if unit.id is None or unit.institutional_id is None:
                continue

            chosen_role = pick_role_for_institutional_id(roles, unit.institutional_id)
            if not chosen_role:
                continue

            await self.unit_user_service.upsert(
                unit_id=unit.id,
                user_id=user.id,
                role=chosen_role,
            )

        logger.info(
            "User units synced",
            extra={"user_id": user_id, "unit_count": len(units)},
        )

        return True
