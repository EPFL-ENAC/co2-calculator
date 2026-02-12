"""User schemas for API request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, computed_field

from app.models import UserBase
from app.models.user import Role, UserProvider


class UserRead(UserBase):
    """Schema for reading user data (OAuth-only users).

    Matches the /auth/me response format with hierarchical roles and permissions.
    Permissions are calculated on-the-fly from roles, not stored in DB.
    """

    id: int
    display_name: Optional[str] = None
    email: EmailStr
    last_login: Optional[datetime] = None
    provider: UserProvider

    @computed_field
    def is_user_test(self) -> Optional[bool]:
        """Indicates if user is a test user (from test login endpoint).

        Computed from the provider field - returns True if provider is TEST,
        None otherwise (omitted from response for production users).
        This is the authoritative way to check test users, not email patterns.
        """
        if self.provider == UserProvider.TEST:
            return True
        return None

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
    provider: UserProvider = UserProvider.DEFAULT


class UserUpdate(BaseModel):
    """Schema for updating a user in backoffice."""

    display_name: Optional[str] = None
    roles: Optional[List[Role]] = None
