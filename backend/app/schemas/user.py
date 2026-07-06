"""User schemas for API request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, computed_field

from app.models.user import Role, UserBase, UserProvider
from app.schemas.unit import UnitWithUserRole
from app.schemas.year_configuration import YearConfigurationListItem


class UserRead(UserBase):
    """Schema for reading user data (OAuth-only users).

    Matches the GET /v1/session response format with hierarchical roles and permissions.
    Permissions are calculated on-the-fly from roles, not stored in DB.
    """

    id: int
    display_name: Optional[str] = None
    email: EmailStr
    last_login: Optional[datetime] = None
    provider: UserProvider
    institutional_id: str

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
        """Calculate permissions dynamically on every GET /v1/session call."""
        return self.calculate_permissions()


class SessionRead(BaseModel):
    """Bootstrap payload for ``GET /v1/session``.

    Bundles everything the frontend needs at app-init in a single call: the
    current user (unchanged ``UserRead`` shape), the units the user can access,
    and the globally-configured years for the workspace year selector. This
    collapses what used to be three separate calls (``/session`` + ``/users/units``
    + ``/year-configuration/``) into one.
    """

    user: UserRead
    units: List[UnitWithUserRole]
    configured_years: List[YearConfigurationListItem]


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
