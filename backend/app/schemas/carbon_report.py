"""Carbon report schemas for API request/response validation."""

from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import ModuleStatus


class CarbonReportBase(BaseModel):
    """Base carbon report schema."""

    year: int
    unit_id: int


class CarbonReportCreate(CarbonReportBase):
    """Schema for creating a carbon report."""

    pass


class CarbonReportRead(CarbonReportBase):
    """Schema for reading a carbon report."""

    id: int

    class Config:
        from_attributes = True


class CarbonReportUpdate(BaseModel):
    """Schema for updating a carbon report."""

    year: Optional[int] = None
    unit_id: Optional[int] = None


# CarbonReportModule schemas
class CarbonReportModuleBase(BaseModel):
    """Base schema for carbon report module."""

    carbon_report_id: int
    module_type_id: int
    status: int = Field(default=ModuleStatus.NOT_STARTED)


class CarbonReportModuleCreate(BaseModel):
    """Schema for creating a carbon report module (carbon_report_id set by path)."""

    module_type_id: int
    status: int = Field(default=ModuleStatus.NOT_STARTED)


class CarbonReportModuleRead(BaseModel):
    """Schema for reading a carbon report module."""

    id: int
    carbon_report_id: int
    module_type_id: int
    status: int

    class Config:
        from_attributes = True


class CarbonReportModuleUpdate(BaseModel):
    """Schema for updating a carbon report module status."""

    status: int = Field(
        ...,
        ge=ModuleStatus.NOT_STARTED,
        le=ModuleStatus.VALIDATED,
        description="Module status: 0=not_started, 1=in_progress, 2=validated",
    )
