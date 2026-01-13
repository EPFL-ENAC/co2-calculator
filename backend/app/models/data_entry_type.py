"""Data entry type model for defining subcategories within module types."""

from typing import Optional

from sqlmodel import Field, SQLModel


class DataEntryTypeBase(SQLModel):
    """Base data entry type model with shared fields."""

    name: str = Field(
        nullable=False,
        index=True,
        description="Data entry type name (e.g., 'student', 'member', 'scientific', 'it')",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the data entry type",
    )
    module_type_id: int = Field(
        foreign_key="module_types.id",
        nullable=False,
        index=True,
        description="Reference to parent module type",
    )


class DataEntryType(DataEntryTypeBase, table=True):
    """
    Data entry type table for defining subcategories/variants within module types.

    Examples:
    - For headcount: student, member, staff
    - For equipment: scientific, it, other
    - For travel: flight, train, car
    """

    __tablename__ = "data_entry_types"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<DataEntryType {self.id}: {self.name} "
            f"(module_type_id={self.module_type_id})>"
        )
