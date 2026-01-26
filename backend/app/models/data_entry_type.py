"""Variant type model for defining subcategories within module types."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class DataEntryTypeEnum(int, Enum):
    member = 1
    student = 2
    scientific = 9
    it = 10
    other = 11
    trips = 20
    building = 30
    energy_mix = 100


class DataEntryTypeBase(SQLModel):
    """Base variant type model with shared fields."""

    name: str = Field(
        nullable=False,
        index=True,
        description="Variant type name (e.g., 'student', 'member', 'scientific', 'it')",
    )
    module_type_id: int = Field(
        foreign_key="module_types.id",
        nullable=False,
        index=True,
        description="Reference to parent module type",
    )


class DataEntryType(DataEntryTypeBase, table=True):
    """
    Variant type table for defining subcategories within module types.

    Examples:
    - For headcount: student, member, staff
    - For equipment: scientific, it, other
    - For travel: flight, train, car
    """

    __tablename__ = "data_entry_types"

    # Primary key field is an integer ID that DataEntryTypeEnum can map to
    # to avoid having SQL + code desync issues. let's keep it optional for SQLModel
    # RULE of thumb: if generic code creates the object, make it optional to use Enum

    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"""<DataEntryType {self.id}: {self.name}
        "(module_type_id={self.module_type_id})>"""
