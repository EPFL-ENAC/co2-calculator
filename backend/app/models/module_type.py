"""Module type model for classifying different module categories."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


# enum - used in other files
class ModuleTypeEnum(int, Enum):
    """
    How the data entered the system.

    Current:
    - api: direct API call
    - csv: CSV file upload

    Potential future values:
    - webhook: event-driven external push
    - sync: scheduled integration sync
    - import_job: background/batch import
    - manual: manual user entry
    """

    # todo: match with actual module types in db! (during seed?)
    headcount = 1
    professional_travel = 2
    infrastructure = 3
    equipment_electric_consumption = 4
    purchase = 5
    internal_services = 6
    external_cloud = 7


class ModuleTypeBase(SQLModel):
    """Base module type model with shared fields."""

    name: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Module type name (e.g., 'headcount', 'equipment', 'travel')",
    )


class ModuleType(ModuleTypeBase, table=True):
    """
    Module type table for classifying different module categories.

    Examples: headcount, equipment, travel, purchases, etc.
    """

    __tablename__ = "module_types"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<ModuleType {self.id}: {self.name}>"
