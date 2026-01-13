"""User model for authentication and authorization."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union

from pydantic import BaseModel

if TYPE_CHECKING:
    pass

from sqlmodel import JSON, Column, Field, SQLModel


class RoleName(str, Enum):
    CO2_USER_STD = "co2.user.std"
    CO2_USER_PRINCIPAL = "co2.user.principal"
    CO2_USER_SECONDARY = "co2.user.secondary"
    CO2_BACKOFFICE_STD = "co2.backoffice.std"
    CO2_BACKOFFICE_ADMIN = "co2.backoffice.admin"
    CO2_SERVICE_MGR = "co2.service.mgr"
    # it's not used in the code, but kept for backward compatibility
    CO2_INVENTORY_VIEWER = "co2.inventory.data"


class GlobalScope(BaseModel):
    scope: str = "global"


class RoleScope(BaseModel):
    provider_code: Optional[str] = None
    affiliation: Optional[str] = None


class Role(BaseModel):
    role: RoleName
    on: Union[RoleScope, GlobalScope]


class UserBase(SQLModel):
    # Role-based access control (hierarchical structure)
    # Format: [{"role": "co2.user.std", "on": {"unit": "12345"}}]
    roles_raw: Optional[List[dict]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Raw roles data for DB storage (from provider)",
    )

    @property
    def roles(self) -> List[Role]:
        if self.roles_raw:
            return [Role(**r) if isinstance(r, dict) else r for r in self.roles_raw]
        return []

    @roles.setter
    def roles(self, value: List[Role]):
        self.roles_raw = [
            {
                **r.model_dump(),
                "role": r.role.value if isinstance(r.role, Enum) else r.role,
            }
            for r in value
        ]

    last_login: Optional[datetime] = Field(default=None, nullable=True)

    def calculate_permissions(self) -> dict:
        """Calculate permissions dynamically based on current user roles.

        This method calculates permissions on-the-fly from the user's roles
        using the calculate_user_permissions utility function.
        Permissions are NOT stored in the database.

        Returns:
            dict: Calculated permissions structure
        """
        from app.utils.permissions import calculate_user_permissions

        return calculate_user_permissions(self.roles)


class User(UserBase, table=True):
    """User model representing authenticated users in the system."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    code: str = Field(
        unique=True,
        index=True,
        description="Provider-assigned user code (SCIPER for EPFL)",
    )
    provider: str = Field(
        nullable=False,
        description="Sync source provider (accred, default, test)",
    )
    email: str = Field(unique=True, index=True, nullable=False)
    display_name: Optional[str] = Field(default=None, nullable=True)
    function: Optional[str] = Field(
        default=None,
        nullable=True,
        description="User function/title (e.g., 'Professor', 'PhD Student')",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role (any scope).

        Args:
            role: Role name to check (e.g., "co2.user.std")

        Returns:
            True if user has the role with any scope
        """
        if not self.roles:
            return False
        return any(r.role == role for r in self.roles)

    def has_role_global(self, role: str) -> bool:
        """Check if user has a specific role with global scope.

        Args:
            role: Role name (e.g., "co2.backoffice.admin")

        Returns:
            True if user has the role with global scope
        """
        if not self.roles:
            return False
        return any(r.role == role and isinstance(r.on, GlobalScope) for r in self.roles)

    def calculate_permissions(self) -> dict:
        """Calculate permissions based on current user roles.

        This method dynamically calculates permissions from the user's roles
        using the calculate_user_permissions utility function.

        Returns:
            dict: Calculated permissions structure
        """
        from app.utils.permissions import calculate_user_permissions

        return calculate_user_permissions(self.roles)

    def refresh_permissions(self) -> None:
        """Recalculate and update the permissions field.

        This method updates the user's stored permissions based on their current roles.
        Call this after modifying user roles to keep permissions in sync.
        """
        self.permissions = self.calculate_permissions()
