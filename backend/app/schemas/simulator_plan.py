"""Simulator plan schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.carbon_report import CarbonReportModuleRead


def _validate_plan_name(value: str) -> str:
    """Strip and validate a plan name (it is a single URL path segment)."""
    value = value.strip()
    if not value:
        raise ValueError("Plan name cannot be empty")
    if "/" in value:
        raise ValueError("Plan name cannot contain '/'")
    return value


class SimulatorPlanCreate(BaseModel):
    """Schema for creating a simulator plan.

    ``name`` is optional: when omitted, the service assigns the next
    available default name (new-project, new-project-2, ...).
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_plan_name(value)


class SimulatorPlanUpdate(BaseModel):
    """Schema for updating a simulator plan (PATCH semantics: absent = keep).

    Setting/changing the year range syncs the plan's per-year reports:
    missing years are created, out-of-range years are deleted with their
    entries (destructive by design).
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    start_year: Optional[int] = Field(default=None, ge=1000, le=9999)
    end_year: Optional[int] = Field(default=None, ge=1000, le=9999)
    is_viewable_by_unit_members: Optional[bool] = None
    is_grant_proposal: Optional[bool] = None
    default_reference_year: Optional[int] = Field(default=None, ge=1000, le=9999)
    """Reference year for year reports newly created by this range change.

    The workspace year the planner was opened from. Applied (with the usual
    prefill) only to reports the sync creates; existing reports keep theirs.
    """

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_plan_name(value)


class SimulatorPlanReferenceYearUpdate(BaseModel):
    """Schema for setting the baseline year of one plan-year report.

    reference_year: Optional[int] = Field(default=None, ge=1000, le=9999)
    """
    ``None`` removes the reference year: the prefilled modules are emptied
    (same wipe as a change) and the year becomes manual-input.
    """
    is_grant: bool = False
    """
    ``is_grant`` disambiguates the Project Grant report from the year report
    sharing its year (the grant report is anchored to the plan's start year).
    """

    reference_year: Optional[int] = Field(default=None, ge=1000, le=9999)


class SimulatorPlanRead(BaseModel):
    """Schema for reading a simulator plan."""

    id: int
    unit_id: int
    name: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    is_viewable_by_unit_members: bool = False
    default_factor_year: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    creator_name: Optional[str] = None
    total_tonnes_co2eq: Optional[float] = None
    can_manage: bool = False

    class Config:
        from_attributes = True


class SimulatorPlanYearRead(BaseModel):
    """One plan-year report with its modules, for the planner page."""

    id: int
    year: int
    reference_year: Optional[int] = None
    is_grant: bool = False
    budget: Optional[float] = None
    budget_currency: Optional[str] = None
    stats: Optional[dict] = None
    modules: list[CarbonReportModuleRead] = []

    class Config:
        from_attributes = True
