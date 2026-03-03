"""API dependencies for dependency injection."""

from app.core.security import (
    check_permission,
    get_current_active_user,
    get_current_active_user_with_any_role,
    get_current_user,
    is_permitted,
)
from app.db import get_db

# Re-export commonly used dependencies
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "get_current_active_user_with_any_role",
    "is_permitted",
    "check_permission",
]
