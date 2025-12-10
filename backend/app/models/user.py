"""User model for authentication and authorization."""

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

    # # --------------------------
    # # LOAD FROM DB  → convert roles_raw → roles (Role objects)
    # # --------------------------
    # @model_validator(mode="before")
    # def load_roles(cls, values):
    #     if isinstance(values, dict):
    #         raw = values.get("roles_raw")
    #         provided_roles = values.get("roles")
    #     else:
    #         provided_roles = getattr(values, "roles", None)
    #         raw = getattr(values, "roles_raw", None)

    #     # If "roles" is already set explicitly (e.g. during create() / update())
    #     # then don't overwrite it.
    #     if provided_roles is not None:
    #         return values

    #     if isinstance(raw, list):
    #         roles: list[Role] = []
    #         for r in raw:
    #             if isinstance(r, dict):
    #                 # Convert string role → enum
    #                 role_val = r.get("role")
    #                 if isinstance(role_val, str):
    #                     r = {**r, "role": RoleName(role_val)}
    #                 roles.append(Role(**r))
    #             else:
    #                 # Already a Role object
    #                 roles.append(r)

    #         values["roles"] = roles

    #     return values

    # # --------------------------
    # # DUMP TO DB  → convert roles → roles_raw (dicts)
    # # --------------------------
    # @model_validator(mode="after")
    # def dump_roles(self):
    #     def role_to_dict(role: Role):
    #         d = role.model_dump()
    #         if isinstance(d.get("role"), Enum):
    #             d["role"] = d["role"].value
    #         return d

    #     self.roles_raw = [role_to_dict(r) for r in self.roles]
    #     return self

    # @classmethod
    # @field_validator("roles", mode="after", check_fields=False)
    # def deserialize_roles(cls, v):
    #     # Convert dicts back to Role objects after loading from DB
    #     if isinstance(v, list):
    #         roles = []
    #         for r in v:
    #             if isinstance(r, dict):
    #                 # Ensure 'role' is an Enum, not a string
    #                 role_val = r.get("role")
    #                 if isinstance(role_val, str):
    #                     r["role"] = RoleName(role_val)
    #                 roles.append(Role(**r))
    #             else:
    #                 roles.append(r)
    #         return roles
    #     return v

    # @classmethod
    # @field_validator("roles", mode="wrap", check_fields=False)
    # def serialize_roles(cls, v, handler):
    #     # Convert Role objects to dicts for JSON serialization
    #     def role_to_dict(role):
    #         d = role.model_dump() if isinstance(role, Role) else role
    #         if isinstance(d.get("role"), Enum):
    #             d["role"] = d["role"].value
    #         return d

    #     if isinstance(v, list):
    #         v = [role_to_dict(r) for r in v]
    #     return handler(v)

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


class User(UserBase, table=True):
    """User model representing authenticated users in the system."""

    __tablename__ = "users"

    id: str = Field(primary_key=True, index=True, description="Sciper in EPFL context")
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

        Args:
            role: Role name to check (e.g., "co2.user.std")

        Returns:
            True if user has the role with any scope
        """
        if not self.roles:
            return False
        return any(r.role == role for r in self.roles)

    def has_role_on(self, role: str, scope_type: str, scope_id: str) -> bool:
        """Check if user has a specific role on a specific resource.

        Args:
            role: Role name (e.g., "co2.user.std")
            scope_type: Scope type (e.g., "unit", "affiliation")
            scope_id: Scope identifier (e.g., "12345")

        Returns:
            True if user has the role on the specified resource
        """
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

        Args:
            role: Role name (e.g., "co2.backoffice.admin")

        Returns:
            True if user has the role with global scope
        """
        if not self.roles:
            return False
        return any(r.role == role and isinstance(r.on, GlobalScope) for r in self.roles)
