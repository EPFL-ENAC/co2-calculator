"""API dependencies for dependency injection."""

from app.core.security import get_current_active_user, get_current_user
from app.db import get_db

# Re-export commonly used dependencies
__all__ = ["get_db", "get_current_user", "get_current_active_user"]
