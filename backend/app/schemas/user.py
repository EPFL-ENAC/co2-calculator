"""User schemas for API request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, computed_field

from app.models import UserBase
from app.models.user import Role


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


class UserCreate(BaseModel):
    """Schema for creating a new user in backoffice."""

    id: str
    email: EmailStr
    display_name: Optional[str] = None
    roles: Optional[List[Role]] = None
    provider: str = "default"
    is_active: bool = True


class UserUpdate(BaseModel):
    """Schema for updating a user in backoffice."""

    display_name: Optional[str] = None
    roles: Optional[List[Role]] = None
    is_active: Optional[bool] = None
