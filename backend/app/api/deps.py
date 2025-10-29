"""API dependencies for dependency injection."""

from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.user import User

# Re-export commonly used dependencies
__all__ = ["get_db", "get_current_user", "get_current_active_user"]


def get_current_user(
    db: Session = Depends(get_db),
) -> Generator[User, None, None]:
    """
    Get current authenticated user.

    This is a convenience re-export of the security dependency.
    """
    return get_current_active_user(db)
