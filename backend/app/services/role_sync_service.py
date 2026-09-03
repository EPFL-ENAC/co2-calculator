"""Role synchronization service for background role updates."""

from datetime import UTC, datetime, timedelta
from enum import Enum

from opentelemetry.metrics import get_meter
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.core.role_priority import pick_role_for_institutional_id
from app.models.user import OwnScope, Role, UnitScope, User
from app.providers.role_provider import RoleProvider, RoleProviderNetworkError
from app.repositories.user_repo import UserRepository
from app.services.unit_service import UnitService
from app.services.unit_user_service import UnitUserService

logger = get_logger(__name__)

# #2623: skips are logged at ERROR (see below) but nothing counted or alerted
# on it. Mirrors the app.db observable-gauge pattern with a plain Counter —
# this is a discrete event, not a poll.
_role_sync_skipped = get_meter(__name__).create_counter(
    "role_sync.skipped",
    unit="{sync}",
    description="Role sync outcomes that left a user's stored roles untouched",
)


class RoleSyncOutcome(str, Enum):
    """Why a role sync ended the way it did.

    ``SKIPPED_*`` outcomes never write to the user: the sync could not
    establish what the roles are, so the stored ones stand (#2531).
    """

    APPLIED = "applied"
    NO_CHANGE = "no_change"
    SKIPPED_TTL = "skipped_ttl"
    SKIPPED_USER_NOT_FOUND = "skipped_user_not_found"
    SKIPPED_PROVIDER_UNAVAILABLE = "skipped_provider_unavailable"
    SKIPPED_SUSPICIOUS_EMPTY = "skipped_suspicious_empty"


class RoleSyncResult(BaseModel):
    """Result of a role synchronization operation."""

    user_id: int
    outcome: RoleSyncOutcome
    has_changed: bool = False
    roles_changed: bool = False
    old_roles: list[Role] = []
    new_roles: list[Role] = []


def _role_sort_key(role) -> tuple:
    """Comparable key for a role, tolerant of dict or model scopes."""
    role_name = role.role if isinstance(role.role, str) else role.role.value
    role_scope = role.on

    if isinstance(role_scope, dict):
        institutional_id = role_scope.get("institutional_id")
        affiliation = role_scope.get("affiliation")

        if institutional_id is not None:
            return (role_name, "institutional", institutional_id)
        if affiliation is not None:
            return (role_name, "affiliation", affiliation)
        return (role_name, "global", None)

    institutional_id = getattr(role_scope, "institutional_id", None)
    if institutional_id is not None:
        return (role_name, "institutional", institutional_id)

    affiliation = getattr(role_scope, "affiliation", None)
    if affiliation is not None:
        return (role_name, "affiliation", affiliation)

    scope_type = (
        type(role_scope).__name__.lower() if role_scope is not None else "global"
    )
    if scope_type == "globalscope":
        return (role_name, "global", None)

    return (role_name, scope_type, None)


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
        role_provider: RoleProvider,
        force: bool = False,
    ) -> RoleSyncResult:
        """Sync user roles from provider.

        Fetches fresh user data from the provider only after the TTL gate
        has been passed, so the external service is never hit for syncs
        that would be skipped anyway.

        Args:
            user_id: User ID to sync
            role_provider: Role provider instance used to fetch live user data
            force: Force sync even if recently synced

        Returns:
            RoleSyncResult with change details
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("User not found for role sync", extra={"user_id": user_id})
            return RoleSyncResult(
                user_id=user_id, outcome=RoleSyncOutcome.SKIPPED_USER_NOT_FOUND
            )

        # Check TTL before hitting the external provider
        if not force and user.last_roles_sync_at:
            time_since_sync = datetime.now(UTC) - user.last_roles_sync_at
            if time_since_sync < self.sync_ttl:
                logger.debug(
                    "Skipping role sync - recently synced",
                    extra={
                        "user_id": user_id,
                        "time_since_sync": str(time_since_sync),
                    },
                )
                return RoleSyncResult(
                    user_id=user_id, outcome=RoleSyncOutcome.SKIPPED_TTL
                )

        # TTL gate passed – fetch fresh data from the external provider now
        old_roles = user.roles or []
        try:
            provider_user = await role_provider.get_user_by_user_id(
                user.institutional_id or ""
            )
        except RoleProviderNetworkError as e:
            # Provider unreachable/unconfigured: keep what we have. Stamped
            # (not left alone) so a burst of near-simultaneous calls doesn't
            # all re-hit the provider — the next attempt waits one TTL period,
            # same backoff the success path already gets (#2539).
            logger.error(
                "Role sync aborted - provider unavailable",
                extra={"user_id": user_id, "error": str(e)},
            )
            _role_sync_skipped.add(
                1, {"outcome": RoleSyncOutcome.SKIPPED_PROVIDER_UNAVAILABLE.value}
            )
            user.last_roles_sync_at = datetime.now(UTC)
            await self.session.commit()
            return RoleSyncResult(
                user_id=user_id,
                outcome=RoleSyncOutcome.SKIPPED_PROVIDER_UNAVAILABLE,
                old_roles=old_roles,
            )

        new_roles = provider_user.get("roles", [])

        # An empty provider response is ambiguous — it means "lost all roles"
        # only if the provider positively says so, and it cannot. Refuse to
        # let an absence of data revoke authority (#2531), unless `force`
        # says a human already confirmed the intent (#2539 admin revoke).
        if not new_roles and old_roles and not force:
            return await self._handle_suspicious_empty(user_id, user, old_roles)

        roles_changed = sorted(_role_sort_key(r) for r in old_roles) != sorted(
            _role_sort_key(r) for r in new_roles
        )

        if not roles_changed:
            logger.debug(
                "No role changes detected",
                extra={"user_id": user_id},
            )
            # A matching non-empty result also confirms the provider is
            # answering again — clear a stale two-strikes timer here too, or
            # a later, unrelated empty response would inherit an old
            # first-seen time instead of starting its own count (#2539).
            user.roles_empty_since = None
            user.last_roles_sync_at = datetime.now(UTC)
            await self.session.commit()
            return RoleSyncResult(
                user_id=user_id,
                outcome=RoleSyncOutcome.NO_CHANGE,
                has_changed=False,
                old_roles=old_roles,
                new_roles=new_roles,
            )

        # Update user roles. A non-empty (or force-applied) result confirms
        # the provider is answering again — clear any pending two-strikes
        # timer (#2539).
        user.roles = new_roles
        user.roles_empty_since = None
        user.last_roles_sync_at = datetime.now(UTC)
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
            outcome=RoleSyncOutcome.APPLIED,
            has_changed=True,
            roles_changed=True,
            old_roles=old_roles,
            new_roles=new_roles,
        )

    async def _handle_suspicious_empty(
        self, user_id: int, user: User, old_roles: list[Role]
    ) -> RoleSyncResult:
        """Two-strikes: don't revoke on the first empty, believe the second (#2539).

        A lone empty response is ambiguous (#2531) and never wipes. A SECOND
        empty response, still empty after 2x the sync TTL since the first,
        has now been confirmed twice running — that is what a genuine
        revocation looks like, so it applies for real. ``roles_empty_since``
        is cleared by the caller on any non-empty result.
        """
        now = datetime.now(UTC)
        first_seen = user.roles_empty_since
        confirmed = bool(first_seen) and now - first_seen >= self.sync_ttl * 2
        _role_sync_skipped.add(
            1, {"outcome": RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY.value}
        )

        if confirmed:
            user.roles = []
            user.roles_empty_since = None
            user.last_roles_sync_at = now
            await self.session.commit()
            logger.error(
                "Role sync applied a confirmed revocation - still zero roles "
                "on a second check",
                extra={"user_id": user.id, "institutional_id": user.institutional_id},
            )
            return RoleSyncResult(
                user_id=user_id,
                outcome=RoleSyncOutcome.APPLIED,
                has_changed=True,
                roles_changed=True,
                old_roles=old_roles,
                new_roles=[],
            )

        # First strike, or still within the confirmation window: keep stored
        # roles. Stamping the timestamp here (not leaving it alone) is the
        # backoff — the next attempt waits one TTL period instead of retrying
        # on every subsequent call within the window (#2539).
        user.roles_empty_since = first_seen or now
        user.last_roles_sync_at = now
        await self.session.commit()
        logger.error(
            "Role sync aborted - provider returned zero roles for a user "
            "that has roles; keeping stored roles, will retry",
            extra={
                "user_id": user.id,
                "institutional_id": user.institutional_id,
                "old_roles_count": len(old_roles),
                "empty_since": user.roles_empty_since.isoformat(),
            },
        )
        return RoleSyncResult(
            user_id=user_id,
            outcome=RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY,
            old_roles=old_roles,
        )

    async def sync_user_units(
        self,
        user_id: int,
        roles: list[Role],
    ) -> bool:
        """Sync user unit associations based on roles.

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
        unit_institutional_ids: set[str] = set()
        for role in roles:
            if isinstance(role.on, (UnitScope, OwnScope)) and role.on.institutional_id:
                unit_institutional_ids.add(role.on.institutional_id)

        if not unit_institutional_ids:
            # No unit roles - delete all associations
            await self.unit_user_service.delete_all_for_user(user.id)
            await self.session.commit()
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
            await self.session.commit()
            return True

        # Delete old associations
        await self.unit_user_service.delete_all_for_user(user.id)
        await self.session.commit()

        # Create new associations
        for unit in units:
            if unit.id is None or unit.institutional_id is None:
                continue

            chosen_role = pick_role_for_institutional_id(roles, unit.institutional_id)
            if not chosen_role:
                continue

            await self.unit_user_service.upsert(
                unit_id=unit.id,
                user_id=user_id,
                role=chosen_role,
            )
        await self.session.commit()

        logger.info(
            "User units synced",
            extra={"user_id": user_id, "unit_count": len(units)},
        )

        return True
