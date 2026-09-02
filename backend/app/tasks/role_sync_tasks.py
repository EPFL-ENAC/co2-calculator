"""Background tasks for role synchronization."""

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.providers.role_provider import get_role_provider
from app.services.role_sync_service import RoleSyncService
from app.services.user_service import UserService

logger = get_logger(__name__)
settings = get_settings()


async def trigger_role_sync_for_user(
    user_id: int,
    force: bool = False,
) -> None:
    """Trigger background role sync for a user.

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

            if not role_provider.supports_background_sync:
                logger.debug(
                    "Role provider has no out-of-band source; skipping sync",
                    extra={"user_id": user_id, "provider": str(user.provider)},
                )
                return

            # Sync roles – provider fetch happens inside service, behind TTL
            # gate. The service reports why it ended (applied / skipped) rather
            # than raising; it never writes on a skip.
            sync_service = RoleSyncService(
                session, sync_ttl_minutes=settings.ROLE_SYNC_TTL_MINUTES
            )
            result = await sync_service.sync_user_roles(
                user_id, role_provider, force=force
            )

            if result.roles_changed:
                logger.info(
                    "Role sync completed - changes detected",
                    extra={"user_id": user_id, "outcome": result.outcome.value},
                )
                await sync_service.sync_user_units(user_id, result.new_roles)
            else:
                logger.debug(
                    "Role sync completed - no role change applied",
                    extra={"user_id": user_id, "outcome": result.outcome.value},
                )

        except Exception as e:
            logger.error(
                "Role sync failed",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            await session.rollback()
