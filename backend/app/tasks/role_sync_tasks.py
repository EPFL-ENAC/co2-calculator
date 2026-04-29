"""Background tasks for role synchronization."""

from app.core.logging import get_logger
from app.db import SessionLocal
from app.providers.role_provider import RoleProviderNetworkError, get_role_provider
from app.services.role_sync_service import RoleSyncService
from app.services.user_service import UserService

logger = get_logger(__name__)


async def trigger_role_sync_for_user(
    user_id: int,
    force: bool = False,
) -> None:
    """
    Trigger background role sync for a user.

    This function:
    1. Fetches user from DB to resolve the role provider
    2. Delegates sync to RoleSyncService, which enforces the TTL gate
       and only fetches from the provider when needed
    3. Syncs unit associations if roles changed

    Args:
        user_id: User ID to sync
        force: Force sync even if recently synced
    """
    async with SessionLocal() as session:
        try:
            user_service = UserService(session)
            user = await user_service.get_by_id(user_id)

            if not user:
                logger.warning(
                    "User not found for role sync",
                    extra={"user_id": user_id},
                )
                return

            # Get role provider
            role_provider = get_role_provider(user.provider)

            # Sync roles – provider fetch happens inside service, behind TTL gate
            sync_service = RoleSyncService(session)
            try:
                result = await sync_service.sync_user_roles(
                    user_id, role_provider, force=force
                )
            except RoleProviderNetworkError as e:
                logger.error(
                    "Role provider unavailable",
                    extra={"user_id": user_id, "error": str(e)},
                )
                return

            if result.has_changed:
                logger.info(
                    "Role sync completed - changes detected",
                    extra={
                        "user_id": user_id,
                        "roles_changed": result.roles_changed,
                    },
                )

                # Sync units if roles changed
                if result.roles_changed:
                    await sync_service.sync_user_units(user_id, result.new_roles)

            else:
                logger.debug(
                    "Role sync completed - no changes",
                    extra={"user_id": user_id},
                )

        except Exception as e:
            logger.error(
                "Role sync failed",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
