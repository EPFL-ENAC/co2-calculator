"""Background tasks for unit synchronization with Accred API."""

from typing import Any, Dict

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.user import UserProvider
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.services.user_service import UserService

logger = get_logger(__name__)


async def sync_units_from_accred_task() -> Dict[str, Any]:
    """
    Background task to sync units and principal users from Accred API.

    This task:
    1. Fetches all units from Accred API
    2. Bulk upserts units into database
    3. Fetches and upserts principal users
    4. Commits changes

    Returns:
        Dict with sync results including counts and status
    """
    try:
        logger.info("Starting unit sync from Accred API")

        async with SessionLocal() as session:
            # Get providers
            provider = get_unit_provider(UserProvider.ACCRED)
            role_provider = get_role_provider(UserProvider.ACCRED)

            # Fetch data from Accred API
            units_raw, principal_users_raw = await provider.fetch_all_units()

            # Map API responses to domain models
            units = [provider.map_api_unit(unit) for unit in units_raw]
            principal_users = [
                role_provider.map_api_user(user) for user in principal_users_raw
            ]

            logger.info(
                f"Fetched {len(units)} units and "
                f"{len(principal_users)} principal users from Accred API"
            )

            # Bulk upsert units
            from app.services.unit_service import UnitService

            unit_service = UnitService(session)
            unit_results = await unit_service.bulk_upsert(units)

            logger.info(f"Upserted {len(units)} units: {unit_results}")

            # Commit units
            await session.commit()

            # Bulk upsert principal users
            user_service = UserService(session)
            user_results = await user_service.bulk_upsert(principal_users)

            logger.info(
                f"Upserted {len(principal_users)} principal users: {user_results}"
            )

            # Commit users
            await session.commit()

            result = {
                "status": "success",
                "units_synced": len(units),
                "users_synced": len(principal_users),
                "unit_results": str(unit_results),
                "user_results": str(user_results),
            }

            logger.info(f"Unit sync completed successfully: {result}")
            return result

    except Exception as e:
        logger.error(f"Unit sync from Accred API failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
