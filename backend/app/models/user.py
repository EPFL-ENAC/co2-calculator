"""User model for authentication and authorization."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union

from pydantic import BaseModel
from sqlalchemy import DateTime
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
    institutional_id: Optional[str] = None
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
        "backoffice.reporting": {"view": bool, "export": bool},
        "backoffice.users": {"view": bool, "edit": bool},
        "backoffice.data_management": {
            "view": bool,
            "edit": bool,
            "export": bool,
            "sync": bool,
        },
        "backoffice.documentation": {"view": bool, "edit": bool},
        "modules.headcount": {"view": bool, "edit": bool},
        "modules.equipment": {"view": bool, "edit": bool},
        "modules.professional_travel": {"view": bool, "edit": bool},
        "modules.buildings": {"view": bool, "edit": bool},
        "modules.purchase": {"view": bool, "edit": bool},
        "modules.research_facilities": {"view": bool, "edit": bool},
        "modules.external_cloud_and_ai": {"view": bool, "edit": bool},
        "modules.process_emissions": {"view": bool, "edit": bool},
    }

    Backoffice Roles (affect backoffice.* ONLY):
    - CO2_BACKOFFICE_METIER: Full backoffice access including:
      * backoffice.reporting: view, export (view reports, generate exports)
      * backoffice.users: view, edit (view user list, assign roles)
      * backoffice.data_management: view, edit, export, sync
        (upload/download CSV, trigger sync)
      * backoffice.documentation: view, edit (view/edit documentation)

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

    # Initialize with no permissions
    permissions: dict[str, list[str]] = {}

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
            return "institutional_id" in s or "affiliation" in s
        return False

    def as_scope_key(s):
        # Note: affiliation-based permissions are not implemented yet,
        # so we return empty string for now to avoid granting permissions
        # based on unrecognized scope formats, but this can be updated in
        # the future when affiliation-based permissions are implemented
        if is_global_scope(s):
            return ""
        if isinstance(s, RoleScope):
            if s.institutional_id and s.institutional_id is not None:
                return f"/{s.institutional_id}"
            if s.affiliation:
                return ""
        elif isinstance(s, dict):
            if "institutional_id" in s and s["institutional_id"] is not None:
                return f"/{s['institutional_id']}"
            if "affiliation" in s:
                return ""
        # Default to no scope if unrecognized format (should not grant permissions)
        return "/?"

    # Helper to merge permission actions and keep unique actions
    def merge_actions(existing, new):
        if existing:
            return list(set(existing) | set(new))
        return new

    for role in roles:
        role_name = role.role if isinstance(role.role, str) else role.role.value
        scope = role.on
        # Note: for now scope will apply only to modules.* permissions, backoffice
        # or system roles will generally be global but can also have institutional scope
        # for future flexibility (currently treated the same as global since we don't
        # have affiliation-based permissions yet)
        scope_key = as_scope_key(scope)

        # BACKOFFICE ROLES - Only affect backoffice.* permissions
        # Compare using enum value for consistency
        if role_name == RoleName.CO2_BACKOFFICE_METIER.value:
            # to stream sync/jobs
            # Backoffice metier can have either global scope or affiliation scope
            # Grants full backoffice access for reporting, docs, and data updates
            if is_global_scope(scope) or is_role_scope(scope):
                permissions["backoffice.reporting"] = merge_actions(
                    permissions.get("backoffice.reporting"), ["view", "export"]
                )
                permissions["backoffice.users"] = merge_actions(
                    permissions.get("backoffice.users"), ["view", "edit", "export"]
                )
                permissions["backoffice.data_management"] = merge_actions(
                    permissions.get("backoffice.data_management"),
                    [
                        "view",
                        "edit",
                        "export",
                        "sync",
                    ],
                )
                permissions["backoffice.documentation"] = merge_actions(
                    permissions.get("backoffice.documentation"), ["view", "edit"]
                )

        # USER ROLES - Only affect modules.* permissions
        elif role_name == RoleName.CO2_USER_PRINCIPAL.value:
            if is_role_scope(scope):
                permissions[f"modules.headcount{scope_key}"] = merge_actions(
                    permissions.get(f"modules.headcount{scope_key}"),
                    ["view", "edit", "sync"],
                )
                permissions[f"modules.equipment{scope_key}"] = merge_actions(
                    permissions.get(f"modules.equipment{scope_key}"),
                    ["view", "edit", "sync"],
                )
                permissions[f"modules.professional_travel{scope_key}"] = merge_actions(
                    permissions.get(f"modules.professional_travel{scope_key}"),
                    [
                        "view",
                        "edit",
                        "sync",
                    ],
                )
                permissions[f"modules.buildings{scope_key}"] = merge_actions(
                    permissions.get(f"modules.buildings{scope_key}"),
                    [
                        "view",
                        "edit",
                        "sync",
                    ],
                )
                permissions[f"modules.purchase{scope_key}"] = merge_actions(
                    permissions.get(f"modules.purchase{scope_key}"),
                    [
                        "view",
                        "edit",
                        "sync",
                    ],
                )
                permissions[f"modules.research_facilities{scope_key}"] = merge_actions(
                    permissions.get(f"modules.research_facilities{scope_key}"),
                    [
                        "view",
                        "edit",
                        "sync",
                    ],
                )
                permissions[f"modules.external_cloud_and_ai{scope_key}"] = (
                    merge_actions(
                        permissions.get(f"modules.external_cloud_and_ai{scope_key}"),
                        [
                            "view",
                            "edit",
                            "sync",
                        ],
                    )
                )
                permissions[f"modules.process_emissions{scope_key}"] = merge_actions(
                    permissions.get(f"modules.process_emissions{scope_key}"),
                    [
                        "view",
                        "edit",
                        "sync",
                    ],
                )
                # Principals can assign co2.user.std role to unit members
                # This grants backoffice.users.edit for unit-scoped role assignment
                permissions["backoffice.users"] = merge_actions(
                    permissions.get("backoffice.users"), ["edit"]
                )

        elif role_name == RoleName.CO2_USER_STD.value:
            if is_role_scope(scope):
                permissions[f"modules.professional_travel{scope_key}"] = merge_actions(
                    permissions.get(f"modules.professional_travel{scope_key}"),
                    [
                        "view",
                        "edit",
                    ],
                )
                permissions[f"modules.external_cloud_and_ai{scope_key}"] = (
                    merge_actions(
                        permissions.get(f"modules.external_cloud_and_ai{scope_key}"),
                        [
                            "view",
                            "edit",
                        ],
                    )
                )

        # SYSTEM ROLES - Affect system.* permissions (and potentially backoffice.*)
        elif role_name == RoleName.CO2_SUPERADMIN.value:
            if is_global_scope(scope):
                # Super admin has full system and backoffice access
                permissions["system.users"] = merge_actions(
                    permissions.get("system.users"), ["edit"]
                )
                permissions["backoffice.reporting"] = merge_actions(
                    permissions.get("backoffice.reporting"), ["view", "export"]
                )
                permissions["backoffice.users"] = merge_actions(
                    permissions.get("backoffice.users"),
                    [
                        "view",
                        "edit",
                        "export",
                    ],
                )
                permissions["backoffice.data_management"] = merge_actions(
                    permissions.get("backoffice.data_management"),
                    [
                        "view",
                        "edit",
                        "export",
                        "sync",
                    ],
                )
                permissions["backoffice.documentation"] = merge_actions(
                    permissions.get("backoffice.documentation"), ["view", "edit"]
                )

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
    institutional_id: str = Field(
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
    last_roles_sync_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last timestamp when roles were synced from provider",
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
