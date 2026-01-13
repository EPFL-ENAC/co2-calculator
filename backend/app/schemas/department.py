"""Unit schemas for API request/response validation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UnitWithUserRole(BaseModel):
    """Schema for unit with current user's role from join."""

    id: int = Field(..., description="EPFL unit/unit ID")
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unit name like 'ENAC-IT4R'",
    )
    current_user_role: str = Field(
        ..., description="Current user's role within this unit"
    )
    principal_user_provider_code: Optional[str] = Field(
        None, description="FK to users.code for principal user"
    )
    principal_user_name: Optional[str] = Field(
        None, description="Display name of the principal user"
    )
    principal_user_function: Optional[str] = Field(
        None, description="Function of the principal user"
    )
    affiliations: list[str] = Field(
        default_factory=list, description="List of affiliated units"
    )

    model_config = ConfigDict(from_attributes=True)


class UnitBase(BaseModel):
    """Base unit schema with common fields."""

    id: int = Field(..., description="CO2 unit internal ID")
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unit name like 'ENAC-IT4R'",
    )
    cost_centers: list[str] = Field(
        default_factory=list, description="List of cost center codes"
    )
    code: str = Field(..., description="Provider-assigned unit code")
    principal_user_provider_code: str = Field(
        ..., description="FK to users.code for principal user"
    )

    affiliations: Optional[list[str]] = Field(
        default_factory=list, description="List of affiliated units"
    )


class UnitCreate(UnitBase):
    """Schema for creating a new unit."""

    pass


class UnitRead(UnitBase):
    """Schema for reading unit data."""

    id: int
    code: str
    name: str
    cost_centers: list[str]
    principal_user_provider_code: str

    model_config = ConfigDict(from_attributes=True)


class UnitList(BaseModel):
    """Schema for paginated unit list."""

    items: list[UnitRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size
