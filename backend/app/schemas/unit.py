"""Resource schemas for API request/response validation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.unit import Unit


class UnitWithUserRole(BaseModel):
    """Schema for unit with current user's role from join."""

    id: int = Field(..., description="EPFL unit/unit ID")
    name: str = Field(
        ..., min_length=1, max_length=255, description="Unit name like 'ENAC-IT4R'"
    )
    current_user_role: str = Field(
        ..., description="Current user's role within this unit"
    )
    principal_user_institutional_id: Optional[str] = Field(
        None, description="Principal user provider code"
    )
    principal_user_name: Optional[str] = Field(
        None, description="Principal user full name"
    )
    principal_user_function: Optional[str] = Field(
        None, description="Principal user function/title"
    )
    affiliations: list[str] = Field(
        default_factory=list, description="List of affiliated units/units"
    )

    model_config = ConfigDict(from_attributes=True)


class UnitCreate(Unit):
    """Schema for creating a new unit."""

    pass


class UnitRead(Unit):
    """Schema for reading resource data."""

    id: int
    name: str
    principal_user_institutional_id: str


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
