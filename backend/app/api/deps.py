"""API dependencies for dependency injection."""

from app.core.security import (
    check_permission,
    get_current_user,
    get_current_user_detached,
    is_permitted,
)
from app.db import get_db

# Re-export commonly used dependencies
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_user_detached",
    "is_permitted",
    "check_permission",
]
