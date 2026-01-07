"""Module type model for classifying different module categories."""

from typing import Optional

from sqlmodel import Field, SQLModel


class ModuleTypeBase(SQLModel):
    """Base module type model with shared fields."""

    name: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Module type name (e.g., 'headcount', 'equipment', 'travel')",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the module type",
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
