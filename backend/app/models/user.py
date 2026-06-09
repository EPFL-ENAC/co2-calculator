"""User model for authentication and authorization."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Annotated, List, Literal, Optional, Union

from pydantic import BaseModel
from pydantic import Field as PydanticField
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
    kind: Literal["global"] = "global"


class UnitScope(BaseModel):
    kind: Literal["unit"] = "unit"
    institutional_id: str


class OwnScope(BaseModel):
    kind: Literal["own"] = "own"
    # The unit the records live in. The owner is always the authenticated
    # current_user, so it is intentionally NOT stored on the scope.
    institutional_id: str


class AffiliationScope(BaseModel):
    kind: Literal["affiliation"] = "affiliation"
    affiliation: str


# Discriminated union: the scope ``kind`` makes the own / unit / global /
# affiliation boundary explicit (matches the permission matrix) instead of
# inferring it from the role.
Scope = Annotated[
    Union[GlobalScope, UnitScope, OwnScope, AffiliationScope],
    PydanticField(discriminator="kind"),
]


class Role(BaseModel):
    role: RoleName
    on: Scope


class UserProvider(int, Enum):
    ACCRED = 0
    DEFAULT = 1
    TEST = 2


def calculate_user_permissions(roles: List[Role]) -> dict:
    """Calculate permissions based on user roles.

    This function maps role-based access control to permission-based access control.
    It processes all user roles and generates a comprehensive permissions structure.

    IMPORTANT: Role domains are independent:
    - Backoffice roles (CO2_BACKOFFICE_METIER) ONLY grant backoffice.* permissions
    - User roles (CO2_USER_*) ONLY grant modules.* permissions
    - CO2_SUPERADMIN grants every backoffice.* page (global)
    - A person can have multiple roles, and permissions combine

    The model is page-driven (#862): one permission per backoffice page.
    Values are lists of action strings (e.g. ["view", "edit"]); module paths
    carry a trailing "/<institutional_id>" for unit-scoped grants.

    Permission Structure (flat with dot notation):
    {
        "backoffice.reporting": [...],          # affiliation-scoped for metier
        "backoffice.users": [...],
        "backoffice.documentation": [...],
        "backoffice.ui_texts": [...],
        "backoffice.configuration": [...],      # super admin only
        "backoffice.pipeline_operations": [...],  # super admin only
        "backoffice.logs": [...],               # super admin only
        "modules.<name>/<institutional_id>": [...],
    }

    Backoffice Roles (affect backoffice.* ONLY):
    - CO2_BACKOFFICE_METIER: backoffice.reporting (affiliation-scoped),
      and scope-less backoffice.users, backoffice.documentation,
      backoffice.ui_texts. No configuration / pipeline_operations / logs.
    - CO2_SUPERADMIN: global (bare) grants on every backoffice page above,
      including configuration / pipeline_operations / logs.

    User Roles (affect modules.* ONLY):
    - CO2_USER_PRINCIPAL: Full module access (view + edit + sync) for the unit
    - CO2_USER_STD: View and edit access to professional_travel and
      external_cloud_and_ai (own records only - enforced via resource policy)

    Args:
        roles: List of Role objects containing role name and scope

    Returns:
        dict: Flat permissions object with dot-notation keys
    """
    if not roles:
        return {}

    # Initialize with no permissions
    permissions: dict[str, list[str]] = {}

    def as_scope_key(scope) -> str:
        # Encode the scope BREADTH in the permission key so the flat dict is
        # self-describing for both the backend resolver and the frontend:
        #   global      → ""             (bare key)
        #   unit        → "/<unit>"      (all records in the unit)
        #   own         → "/<unit>/own"  (own records only; owner = current_user)
        #   affiliation → "/<aff>"       (backoffice sub-perimeter, #459)
        # A missing identifier falls through to the "/?" sentinel — defensive
        # against an upstream bug producing an empty institutional_id/affiliation.
        if scope.kind == "global":
            return ""
        if scope.kind == "unit":
            return f"/{scope.institutional_id}" if scope.institutional_id else "/?"
        if scope.kind == "own":
            return f"/{scope.institutional_id}/own" if scope.institutional_id else "/?"
        if scope.kind == "affiliation":
            return f"/{scope.affiliation}" if scope.affiliation else "/?"
        return "/?"

    def merge_actions(existing, new):
        # Merge permission actions, keeping them unique.
        if existing:
            return list(set(existing) | set(new))
        return new

    for role in roles:
        role_name = role.role if isinstance(role.role, str) else role.role.value
        scope = role.on
        scope_key = as_scope_key(scope)

        # BACKOFFICE ROLES - Only affect backoffice.* permissions
        # Compare using enum value for consistency
        if role_name == RoleName.CO2_BACKOFFICE_METIER.value:
            # CO2_BACKOFFICE_METIER is always sub-perimeter-bound: ACCRED only
            # ever produces an AffiliationScope (LVL3) for this role. Only
            # CO2_SUPERADMIN gets cross-affiliation reach (the bare backoffice.*
            # keys below). Any other scope kind is unconfigured and emits
            # nothing — gate_backoffice will 403 the caller, surfacing the
            # misconfiguration rather than masking it.
            if scope.kind == "affiliation":
                # Reporting is the only affiliation-scoped backoffice area
                # (#862): it filters report data by sub-perimeter, so it
                # carries the ``/<aff>`` suffix and is the affiliation anchor.
                # Users, documentation and UI-text editing have no per-unit
                # data to filter, so metier receives them scope-less.
                # Configuration, pipeline operations and logs are Super Admin
                # only and are not granted here.
                permissions[f"backoffice.reporting{scope_key}"] = merge_actions(
                    permissions.get(f"backoffice.reporting{scope_key}"),
                    ["view", "export"],
                )
                permissions["backoffice.users"] = merge_actions(
                    permissions.get("backoffice.users"),
                    ["view", "edit", "export"],
                )
                permissions["backoffice.documentation"] = merge_actions(
                    permissions.get("backoffice.documentation"),
                    ["view", "edit"],
                )
                permissions["backoffice.ui_texts"] = merge_actions(
                    permissions.get("backoffice.ui_texts"),
                    ["view", "edit"],
                )
                # to be removed later on when new right is available
                permissions["backoffice.configuration"] = merge_actions(
                    permissions.get("backoffice.configuration"), ["view", "edit"]
                )
                permissions["backoffice.pipeline_operations"] = merge_actions(
                    permissions.get("backoffice.pipeline_operations"),
                    ["view", "edit"],
                )
        # USER ROLES - Only affect modules.* permissions
        elif role_name == RoleName.CO2_USER_PRINCIPAL.value:
            # Principal is unit-scoped: full module access across the unit.
            if scope.kind == "unit":
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
                # Unit-level affordance: validating a module's status. The
                # frontend gates the sidebar validate button on this key;
                # standard (own) users never receive it, so the button is
                # hidden for them. Backend PATCH stays enforced by
                # ``require_module_unit_scope``.
                permissions[f"module.status{scope_key}"] = merge_actions(
                    permissions.get(f"module.status{scope_key}"),
                    ["edit"],
                )

        elif role_name == RoleName.CO2_USER_STD.value:
            # Standard user is own-scoped: own records only. The "/<unit>/own"
            # key keeps them out of unit-level gates (e.g. PATCH module status).
            if scope.kind == "own":
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

        # SUPER ADMIN - global access to every backoffice page (#862)
        elif role_name == RoleName.CO2_SUPERADMIN.value:
            if scope.kind == "global":
                # Bare (global) grants on every backoffice page. reporting is
                # bare here; CO2_BACKOFFICE_METIER gets it affiliation-scoped.
                # configuration / pipeline_operations / logs are Super Admin
                # only — they replace the former system.users gate.
                permissions["backoffice.reporting"] = merge_actions(
                    permissions.get("backoffice.reporting"), ["view", "export"]
                )
                permissions["backoffice.users"] = merge_actions(
                    permissions.get("backoffice.users"), ["view", "edit", "export"]
                )
                permissions["backoffice.documentation"] = merge_actions(
                    permissions.get("backoffice.documentation"), ["view", "edit"]
                )
                permissions["backoffice.ui_texts"] = merge_actions(
                    permissions.get("backoffice.ui_texts"), ["view", "edit"]
                )
                permissions["backoffice.configuration"] = merge_actions(
                    permissions.get("backoffice.configuration"), ["view", "edit"]
                )
                permissions["backoffice.pipeline_operations"] = merge_actions(
                    permissions.get("backoffice.pipeline_operations"),
                    ["view", "edit"],
                )
                permissions["backoffice.logs"] = merge_actions(
                    permissions.get("backoffice.logs"), ["view"]
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
