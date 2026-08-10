"""Carbon report schemas for API request/response validation."""

from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import ModuleStatus


class CarbonReportBase(BaseModel):
    """Base carbon report schema."""

    year: int
    reference_year: Optional[int] = None
    unit_id: int
    carbon_project_id: Optional[int] = None
    is_grant: bool = False
    budget: Optional[float] = None
    budget_currency: Optional[str] = None


class CarbonReportCreate(CarbonReportBase):
    """Schema for creating a carbon report."""

    pass


class CarbonReportRead(CarbonReportBase):
    """Schema for reading a carbon report."""

    id: int
    stats: Optional[dict] = None
    last_updated: Optional[int] = None
    completion_progress: Optional[str] = None
    overall_status: int = ModuleStatus.NOT_STARTED

    class Config:
        from_attributes = True


class CarbonReportUpdate(BaseModel):
    """Schema for updating a carbon report."""

    year: Optional[int] = None
    reference_year: Optional[int] = None
    unit_id: Optional[int] = None
    carbon_project_id: Optional[int] = None


# CarbonReportModule schemas
class CarbonReportModuleBase(BaseModel):
    """Base schema for carbon report module."""

    carbon_report_id: int
    module_type_id: int
    status: int = Field(default=ModuleStatus.NOT_STARTED)


class CarbonReportModuleCreate(CarbonReportModuleBase):
    """Schema for creating a carbon report module (carbon_report_id set by path)."""

    pass


class CarbonReportModuleRead(BaseModel):
    """Schema for reading a carbon report module."""

    id: int
    carbon_report_id: int
    module_type_id: int
    status: int
    is_active: bool = True
    budgets: Optional[dict[str, float]] = None
    stats: Optional[dict] = None

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


class CarbonReportModuleActiveUpdate(BaseModel):
    """Schema for toggling a module's Active flag (Simulator Plan)."""

    is_active: bool


class CarbonReportBudgetUpdate(BaseModel):
    """Schema for setting a Project Grant report's total budget (#1978).

    ``budget_currency`` is a lowercase code from the purchase module's
    currency set; like purchase entries it is not validated server-side.
    """

    budget: Optional[float] = Field(default=None, ge=0)
    budget_currency: Optional[str] = Field(default=None, min_length=3, max_length=8)


class CarbonReportReferencePercentageUpdate(BaseModel):
    """Schema for the grant equipment global percentage (#1981)."""

    percentage: float = Field(ge=0, le=100)


class CarbonReportSubmoduleBudgetUpdate(BaseModel):
    """Schema for setting a grant submodule's share of the budget (#1978).

    A null ``budget`` clears the submodule's entry.
    """

    submodule: str = Field(min_length=1, max_length=100)
    budget: Optional[float] = Field(default=None, ge=0)
