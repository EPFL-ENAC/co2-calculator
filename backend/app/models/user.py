"""User model for authentication and authorization."""

import warnings
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union

from pydantic import BaseModel

if TYPE_CHECKING:
    pass

# from sqlalchemy import JSON, Boolean, DateTime, Integer, String
# from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


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
    unit: Optional[str] = None
    affiliation: Optional[str] = None


class Role(BaseModel):
    role: RoleName
    on: Union[RoleScope, GlobalScope]


class UserBase(SQLModel):
    # Role-based access control (hierarchical structure)
    # Format: [{"role": "co2.user.std", "on": {"unit": "12345"}}]
    # roles: List[Role] = Field(
    #     default_factory=list,
    #     description="User roles with hierarchical scopes",
    # )
    # roles: List[Role] = Field(
    #     default_factory=list,
    #     description="User roles with hierarchical scopes",
    #     exclude=True,
    # )

    roles_raw: Optional[List[dict]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Raw roles data for DB storage",
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

    # Status
    is_active: bool = Field(default=True)

    last_login: Optional[datetime] = Field(default=None, nullable=True)
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    created_by: Optional[str] = Field(default=None, index=True)
    updated_by: Optional[str] = Field(default=None, index=True)

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

    id: str = Field(primary_key=True, index=True, description="Sciper in EPFL context")
    provider: str = Field(
        nullable=False,
        description="Authentication provider (e.g. default, test, accred, ...)",
    )
    email: str = Field(unique=True, index=True, nullable=False)
    display_name: Optional[str] = Field(default=None, nullable=True)

    # # Relationship to UnitUser
    # unit_users: list["UnitUser"] = Relationship(
    #     back_populates="user",
    #     sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    # )

    # # Relationships
    # units: list["Unit"] = Relationship(back_populates="users", link_model=UnitUser)

    # resources: list["Resource"] = Relationship(
    #     back_populates="user",
    # )

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role (any scope).

        DEPRECATED: Use permission-based checks via require_permission() or
        check_resource_access() instead of direct role checks in business logic.

        This method remains for internal use (permission calculation, role providers),
        but should not be used in service-level authorization logic.

        Args:
            role: Role name to check (e.g., "co2.user.std")

        Returns:
            True if user has the role with any scope
        """
        warnings.warn(
            "has_role() is deprecated for business logic. "
            "Use permission-based authorization via require_permission() "
            "or check_resource_access() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self.roles:
            return False
        return any(r.role == role for r in self.roles)

    def has_role_on(self, role: str, scope_type: str, scope_id: str) -> bool:
        """Check if user has a specific role on a specific resource.

        DEPRECATED: Use permission-based checks via require_permission() or
        check_resource_access() instead of direct role checks in business logic.

        This method remains for internal use, but should not be used in
        service-level authorization logic.

        Args:
            role: Role name (e.g., "co2.user.std")
            scope_type: Scope type (e.g., "unit", "affiliation")
            scope_id: Scope identifier (e.g., "12345")

        Returns:
            True if user has the role on the specified resource
        """
        warnings.warn(
            "has_role_on() is deprecated for business logic. "
            "Use permission-based authorization via require_permission() "
            "or check_resource_access() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self.roles:
            return False
        for r in self.roles:
            if r.role == role:
                on = r.on
                if (
                    isinstance(on, RoleScope)
                    and getattr(on, scope_type, None) == scope_id
                ):
                    return True
        return False

    def has_role_global(self, role: str) -> bool:
        """Check if user has a specific role with global scope.

        DEPRECATED: Use permission-based checks via require_permission() or
        check_resource_access() instead of direct role checks in business logic.

        This method remains for internal use, but should not be used in
        service-level authorization logic.

        Args:
            role: Role name (e.g., "co2.backoffice.admin")

        Returns:
            True if user has the role with global scope
        """
        warnings.warn(
            "has_role_global() is deprecated for business logic. "
            "Use permission-based authorization via require_permission() "
            "or check_resource_access() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
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
