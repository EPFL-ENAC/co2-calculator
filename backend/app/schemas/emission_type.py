"""Emission type schemas for API requests and responses."""

from typing import Optional

from pydantic import BaseModel, Field


class EmissionTypeBase(BaseModel):
    """Base emission type schema."""

    code: str = Field(..., description="Unique code identifier")
    label: str = Field(..., description="Human-readable label")
    unit: str = Field(default="kg_co2eq", description="Unit of measurement")
    description: Optional[str] = Field(None, description="Detailed description")


class EmissionTypeCreate(EmissionTypeBase):
    """Schema for creating an emission type."""

    pass


class EmissionTypeRead(EmissionTypeBase):
    """Schema for reading an emission type."""

    id: int = Field(..., description="Emission type ID")

    class Config:
        """Pydantic config."""

        from_attributes = True


class EmissionTypeResponse(EmissionTypeRead):
    """API response schema for emission type."""

    pass
