"""Resource schemas for API request/response validation."""

from typing import Optional

from pydantic import BaseModel, Field


class UnitBase(BaseModel):
    """Base unit schema with common fields."""

    id: int = Field(..., description="EPFL unit/department numeric ID")
    name: str = Field(
        ..., min_length=1, max_length=255, description="Unit name like 'ENAC-IT4R'"
    )
    role: str = Field(..., description="User role within the unit")
    principal_user_id: int = Field(..., description="Principal user EPFL numeric ID")
    principal_user_name: str = Field(..., description="Principal user full name")
    principal_user_function: str = Field(
        ..., description="Principal user function/title"
    )
    affiliations: Optional[list[str]] = Field(
        default_factory=list, description="List of affiliated units/departments"
    )
    visibility: str = Field(
        default="private",
        pattern="^(public|private|unit)$",
        description="Visibility level: public, private, or unit",
    )


class UnitCreate(UnitBase):
    """Schema for creating a new unit."""

    pass


class UnitRead(UnitBase):
    """Schema for reading resource data."""

    id: int
    name: str
    role: str
    principal_user_id: int

    class Config:
        from_attributes = True


class UnitList(BaseModel):
    """Schema for paginated resource list."""

    items: list[UnitRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size
