"""User schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import EmailStr, computed_field

from app.models import UserBase


class UserRead(UserBase):
    """Schema for reading user data (OAuth-only users).

    Matches the /auth/me response format with hierarchical roles and permissions.
    Permissions are calculated on-the-fly from roles, not stored in DB.
    """

    id: str
    display_name: Optional[str] = None
    email: EmailStr
    # roles_raw: List[Role] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    @computed_field
    def permissions(self) -> dict:
        """Calculate permissions dynamically from roles on every /auth/me call."""
        return self.calculate_permissions()
