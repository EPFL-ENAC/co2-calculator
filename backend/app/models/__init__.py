"""Database models."""

from sqlmodel import Relationship

from .emission_factor import (
    EmissionFactor,
    EmissionFactorBase,
    PowerFactor,
    PowerFactorBase,
)
from .equipment import (
    Equipment,
    EquipmentBase,
    EquipmentEmission,
    EquipmentEmissionBase,
)
from .headcount import (
    HeadCount,
    HeadCountBase,
    HeadCountCreate,
    HeadCountRead,
    HeadCountUpdate,
)
from .resource import Resource, ResourceBase
from .unit import Unit
from .unit_user import UnitUser
from .user import User, UserBase

# IMPORTANT: Call model_rebuild() BEFORE adding relationships
User.model_rebuild()
Resource.model_rebuild()

# Now add relationships after both classes exist
User.resources = Relationship(
    back_populates="user",
)

Resource.user = Relationship(
    back_populates="resources",
    sa_relationship_kwargs={"foreign_keys": "[Resource.updated_by]"},
)


# After model_rebuild()
Unit.unit_users = Relationship(back_populates="unit")
UnitUser.unit = Relationship(back_populates="unit_users")

User.unit_users = Relationship(back_populates="user")
UnitUser.user = Relationship(back_populates="unit_users")

## implement join later then for equipment power_Factors
# and equipment_emissions and user if needed

__all__ = [
    "Unit",
    "User",
    "UserBase",
    "UnitUser",
    "Resource",
    "ResourceBase",
    "EmissionFactor",
    "EmissionFactorBase",
    "PowerFactor",
    "PowerFactorBase",
    "Equipment",
    "EquipmentBase",
    "EquipmentEmission",
    "EquipmentEmissionBase",
    "HeadCount",
    "HeadCountBase",
    "HeadCountCreate",
    "HeadCountRead",
    "HeadCountUpdate",
]
