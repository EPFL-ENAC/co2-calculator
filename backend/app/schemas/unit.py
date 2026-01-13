"""Resource schemas for API request/response validation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UnitWithUserRole(BaseModel):
    """Schema for unit with current user's role from join."""

    id: int = Field(..., description="EPFL unit/unit ID")
    name: str = Field(
        ..., min_length=1, max_length=255, description="Unit name like 'ENAC-IT4R'"
    )
    current_user_role: str = Field(
        ..., description="Current user's role within this unit"
    )
    principal_user_provider_code: Optional[str] = Field(
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


class UnitBase(BaseModel):
    """Base unit schema with common fields."""

    id: str = Field(..., description="EPFL unit/unit numeric ID")
    name: str = Field(
        ..., min_length=1, max_length=255, description="Unit name like 'ENAC-IT4R'"
    )
    role: str = Field(..., description="User role within the unit")
    principal_user_provider_code: str = Field(
        ..., description="Principal user provider code"
    )
    principal_user_name: str = Field(..., description="Principal user full name")
    principal_user_function: str = Field(
        ..., description="Principal user function/title"
    )
    affiliations: Optional[list[str]] = Field(
        default_factory=list, description="List of affiliated units/units"
    )


class UnitCreate(UnitBase):
    """Schema for creating a new unit."""

    pass


class UnitRead(UnitBase):
    """Schema for reading resource data."""

    id: str
    name: str
    role: str
    principal_user_provider_code: str

    model_config = ConfigDict(from_attributes=True)


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
