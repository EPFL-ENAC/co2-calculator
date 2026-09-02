"""User API endpoints.

NOTE: Most user management endpoints have been removed. Users are managed
internally through OAuth/OIDC authentication only; user information is
available via GET /v1/session. The one exception is admin revoke below
(#2539) — the first use of the long-documented `backoffice.users` (view,
edit, export) permission (see `app.main`'s API description).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.user import User
from app.providers.role_provider import get_role_provider
from app.schemas.unit import UnitWithUserRole
from app.services.role_sync_service import RoleSyncResult, RoleSyncService
from app.services.unit_service import UnitService
from app.services.user_service import UserService

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

# All other user management endpoints removed - users are read-only via
# GET /v1/session. Users are auto-created and updated during OAuth login flow.


@router.get("/units", response_model=list[UnitWithUserRole])
async def list_user_units(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List units with policy authorization.

    This endpoint
    1. User is authenticated via JWT (handled by dependency)
    2. Service layer queries policy engine for filters
    3. Repository applies filters to database query
    4. Only authorized resources are returned

    The policy engine determines which resources the user can see based on:
    - User roles
    - Unit membership
    - Unit visibility
    """
    units = await UnitService(db).get_user_units(current_user)
    logger.info(
        "User requested unit list",
        extra={"user_id": sanitize(current_user.id), "count": len(units)},
    )
    return units


@router.post("/{user_id}/revoke-roles", response_model=RoleSyncResult)
async def revoke_user_roles(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_permission("backoffice.users", "edit")),
) -> RoleSyncResult:
    """Force an immediate, authoritative role check for one user (#2539).

    The declined ``force`` hatch from #2531/#2538, reinstated but reachable
    only here: re-runs the provider check right now (skipping the TTL gate
    and the two-strikes guard) and applies whatever comes back, including
    empty. It does not invent a revocation the provider doesn't confirm —
    if the provider still reports the user's roles, nothing changes.

    For a `JwtClaimsRoleProvider` user there is no out-of-band source to
    re-check (roles only ever come from the JWT at login), so this 400s
    rather than silently no-op'ing.
    """
    target = await UserService(db).get_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    role_provider = get_role_provider(target.provider)
    if not role_provider.supports_background_sync:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This user's role provider has no out-of-band source to "
            "re-check — nothing to revoke against",
        )

    sync_service = RoleSyncService(db, sync_ttl_minutes=settings.ROLE_SYNC_TTL_MINUTES)
    result = await sync_service.sync_user_roles(user_id, role_provider, force=True)
    if result.roles_changed:
        await sync_service.sync_user_units(user_id, result.new_roles)

    logger.info(
        "Admin-triggered role revocation check",
        extra={
            "admin_user_id": sanitize(admin.id),
            "target_user_id": sanitize(user_id),
            "outcome": result.outcome.value,
        },
    )
    return result
