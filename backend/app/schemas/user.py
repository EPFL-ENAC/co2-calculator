"""User schemas for API request/response validation."""

from datetime import datetime

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
    display_name: str | None = None
    email: EmailStr
    last_login: datetime | None = None
    provider: UserProvider
    institutional_id: str

    @computed_field
    def is_user_test(self) -> bool | None:
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

    ``min_configurable_year`` is also echoed on the single-year
    ``YearConfigurationResponse``, but that one only exists once a row has
    been created for the requested year. Bundling it here too gives the
    frontend a source that doesn't depend on any particular year existing —
    e.g. the backoffice year selector can seed its lower bound even when the
    current real-world year has no ``YearConfiguration`` row yet.
    """

    user: UserRead
    units: list[UnitWithUserRole]
    configured_years: list[YearConfigurationListItem]
    min_configurable_year: int


class UserCreate(BaseModel):
    """Schema for creating a new user in backoffice."""

    id: str
    email: EmailStr
    display_name: str | None = None
    roles: list[Role] | None = None
    provider: UserProvider = UserProvider.DEFAULT


class UserUpdate(BaseModel):
    """Schema for updating a user in backoffice."""

    display_name: str | None = None
    roles: list[Role] | None = None
