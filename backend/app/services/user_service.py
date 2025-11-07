"""User service for internal user operations.

NOTE: This service is for internal use only (OAuth flow, system operations).
Public user management has been removed - users are managed via OAuth/OIDC only.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.repositories import user_repo

logger = get_logger(__name__)


async def get_user(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID (internal use)."""
    return await user_repo.get_user_by_id(db, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email (internal use)."""
    return await user_repo.get_user_by_email(db, email)

