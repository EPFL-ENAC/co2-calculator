"""User model for authentication and authorization."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union

from pydantic import BaseModel
from sqlalchemy import Enum as SAEnum

if TYPE_CHECKING:
    pass

from sqlmodel import JSON, Column, Field, SQLModel


# ONLY ONE PLACE TO DEFINE ROLE NAMES
class RoleName(str, Enum):
    CO2_USER_STD = "calco2.user.standard"
    CO2_USER_PRINCIPAL = "calco2.user.principal"
    CO2_BACKOFFICE_METIER = "calco2.backoffice.metier"
    CO2_SUPERADMIN = "calco2.superadmin"


class GlobalScope(BaseModel):
    scope: str = "global"


class RoleScope(BaseModel):
    provider_code: Optional[str] = None
    affiliation: Optional[str] = None


class Role(BaseModel):
    role: RoleName
    on: Union[RoleScope, GlobalScope]


class UserProvider(int, Enum):
    ACCRED = 0
    DEFAULT = 1
    TEST = 2


def calculate_user_permissions(roles: List[Role]) -> dict:
    """Calculate permissions based on user roles.

    This function maps role-based access control to permission-based access control.
    It processes all user roles and generates a comprehensive permissions structure.

    IMPORTANT: Role domains are generally independent, with some exceptions:
    - Backoffice roles (CO2_BACKOFFICE_METIER) ONLY grant backoffice.* permissions
    - User roles (CO2_USER_*) primarily grant modules.* permissions
      Exception: CO2_USER_PRINCIPAL also grants backoffice.users.edit for unit-scoped
      role assignment (to assign co2.user.std to unit members)
    - System roles (CO2_SUPERADMIN) grant system.* permissions
      Exception: CO2_SUPERADMIN also grants full backoffice.* access
    - A person can have multiple roles, and permissions combine

    Permission Structure (flat with dot notation):
    {
        "backoffice.users": {"view": bool, "edit": bool, "export": bool},
        "modules.headcount": {"view": bool, "edit": bool},
        "modules.equipment": {"view": bool, "edit": bool},
        "modules.professional_travel": {"view": bool, "edit": bool},
        "modules.infrastructure": {"view": bool, "edit": bool},
        "modules.purchase": {"view": bool, "edit": bool},
        "modules.internal_services": {"view": bool, "edit": bool},
        "modules.external_cloud_and_ai": {"view": bool, "edit": bool},
    }

    Backoffice Roles (affect backoffice.* ONLY):
    - CO2_BACKOFFICE_METIER: Backoffice administrator with reporting, documentation,
      and data update capabilities (view/edit/export users)

    User Roles (affect modules.* ONLY):
    - CO2_USER_PRINCIPAL: Full module access (view + edit) + can assign co2.user.std
      role to unit members (backoffice.users.edit for unit scope)
    - CO2_USER_STD: View and edit access to professional_travel module
      (own trips only - enforced via resource-level policy)

    System Roles (affect system.* and backoffice.*):
    - CO2_SUPERADMIN: Super administrator with full system and backoffice access
      (system.users.edit for role assignment, backoffice.* for admin access)

    Args:
        roles: List of Role objects containing role name and scope

    Returns:
        dict: Flat permissions object with dot-notation keys
    """
    if not roles:
        return {}

    # Initialize with all permissions set to False
    permissions = {
        "backoffice.users": {"view": False, "edit": False, "export": False},
        "backoffice.files": {"view": False},
        "system.users": {"edit": False},
        "modules.headcount": {"view": False, "edit": False},
        "modules.equipment": {"view": False, "edit": False},
        "modules.professional_travel": {"view": False, "edit": False},
        "modules.infrastructure": {"view": False, "edit": False},
        "modules.purchase": {"view": False, "edit": False},
        "modules.internal_services": {"view": False, "edit": False},
        "modules.external_cloud_and_ai": {"view": False, "edit": False},
    }

    # Helper to check if scope is global (handles both GlobalScope objects and dicts)
    def is_global_scope(s):
        if isinstance(s, GlobalScope):
            return True
        if isinstance(s, dict):
            return s.get("scope") == "global"
        return False

    # Helper to check if scope is role scope (handles both RoleScope objects and dicts)
    def is_role_scope(s):
        if isinstance(s, RoleScope):
            return True
        if isinstance(s, dict):
            return "unit" in s or "affiliation" in s
        return False

    for role in roles:
        role_name = role.role if isinstance(role.role, str) else role.role.value
        scope = role.on

        # BACKOFFICE ROLES - Only affect backoffice.* permissions
        # Compare using enum value for consistency
        if role_name == RoleName.CO2_BACKOFFICE_METIER.value:
            # Backoffice metier can have either global scope or affiliation scope
            # Grants full backoffice access for reporting, docs, and data updates
            if is_global_scope(scope) or is_role_scope(scope):
                permissions["backoffice.users"] = {
                    "view": True,
                    "edit": True,
                    "export": True,
                }
                permissions["backoffice.files"]["view"] = True

        # USER ROLES - Only affect modules.* permissions
        elif role_name == RoleName.CO2_USER_PRINCIPAL.value:
            if is_role_scope(scope):
                permissions["modules.headcount"] = {"view": True, "edit": True}
                permissions["modules.equipment"] = {"view": True, "edit": True}
                permissions["modules.professional_travel"] = {
                    "view": True,
                    "edit": True,
                }
                permissions["modules.infrastructure"] = {"view": True, "edit": True}
                permissions["modules.purchase"] = {"view": True, "edit": True}
                permissions["modules.internal_services"] = {"view": True, "edit": True}
                permissions["modules.external_cloud_and_ai"] = {
                    "view": True,
                    "edit": True,
                }
                # Principals can assign co2.user.std role to unit members
                # This grants backoffice.users.edit for unit-scoped role assignment
                permissions["backoffice.users"]["edit"] = True

        elif role_name == RoleName.CO2_USER_STD.value:
            if is_role_scope(scope):
                permissions["modules.professional_travel"]["view"] = True
                permissions["modules.professional_travel"]["edit"] = True

        # SYSTEM ROLES - Affect system.* permissions (and potentially backoffice.*)
        elif role_name == RoleName.CO2_SUPERADMIN.value:
            if is_global_scope(scope):
                # Super admin has full system and backoffice access
                permissions["system.users"]["edit"] = True
                permissions["backoffice.users"] = {
                    "view": True,
                    "edit": True,
                    "export": True,
                }
                permissions["backoffice.files"]["view"] = True

    return permissions


class UserBase(SQLModel):
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
        return calculate_user_permissions(self.roles)


class User(UserBase, table=True):
    """User model representing authenticated users in the system."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    provider_code: str = Field(
        unique=True,
        index=True,
        description="Provider-assigned user code (SCIPER for EPFL)",
    )
    provider: UserProvider = Field(
        default=UserProvider.DEFAULT.value,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
        ),
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
        if not self.roles:
            return False
        return any(r.role == role for r in self.roles)

    def has_role_global(self, role: str) -> bool:
        if not self.roles:
            return False
        return any(r.role == role and isinstance(r.on, GlobalScope) for r in self.roles)

    def calculate_permissions(self) -> dict:
        return calculate_user_permissions(self.roles)

    def refresh_permissions(self) -> None:
        self.permissions = self.calculate_permissions()
