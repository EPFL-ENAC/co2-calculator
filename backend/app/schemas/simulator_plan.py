"""Simulator plan schemas for API request/response validation."""

from datetime import datetime

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

    name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_plan_name(value)


class SimulatorPlanUpdate(BaseModel):
    """Schema for updating a simulator plan (PATCH semantics: absent = keep).

    Setting/changing the year range syncs the plan's per-year reports:
    missing years are created, out-of-range years are deleted with their
    entries (destructive by design).

    ``with_year_sections`` is not persisted: whether a plan has per-year
    sections is derived from its non-grant reports. Omitted, the sync keeps
    the plan's current shape; ``False`` deletes the per-year reports (the
    plan must then be a grant proposal); ``True`` (re)creates them.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_year: int | None = Field(default=None, ge=1000, le=9999)
    end_year: int | None = Field(default=None, ge=1000, le=9999)
    is_viewable_by_unit_members: bool | None = None
    is_grant_proposal: bool | None = None
    with_year_sections: bool | None = None
    default_reference_year: int | None = Field(default=None, ge=1000, le=9999)
    """Reference year for year reports newly created by this range change.

    The workspace year the planner was opened from. Applied (with the usual
    prefill) only to reports the sync creates; existing reports keep theirs.
    """

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_plan_name(value)


class SimulatorPlanReferenceYearUpdate(BaseModel):
    """Schema for setting the baseline year of one plan-year report.

    ``None`` removes the reference year: the prefilled modules are emptied
    (same wipe as a change) and the year becomes manual-input.

    ``is_grant`` disambiguates the Project Grant report from the year report
    sharing its year (the grant report is anchored to the plan's start year).
    """

    reference_year: int | None = Field(default=None, ge=1000, le=9999)
    is_grant: bool = False


class SimulatorPlanRead(BaseModel):
    """Schema for reading a simulator plan."""

    id: int
    unit_id: int
    name: str
    start_year: int | None = None
    end_year: int | None = None
    is_viewable_by_unit_members: bool = False
    is_grant_proposal: bool = False
    default_factor_year: int | None = None
    created_by: int | None = None
    created_at: datetime | None = None
    creator_name: str | None = None
    total_tonnes_co2eq: float | None = None
    can_manage: bool = False
    #: Set when the PATCH deferred its prefill to a ``simulator_plan_prefill``
    #: job (plan #2050 Track F4). ``None`` means there was nothing to wait
    #: for; otherwise the client polls this job before trusting the year's
    #: entries and stats.
    prefill_job_id: int | None = None

    class Config:
        from_attributes = True


class SimulatorPlanYearRead(BaseModel):
    """One plan-year report with its modules, for the planner page."""

    id: int
    year: int
    reference_year: int | None = None
    is_grant: bool = False
    budget: float | None = None
    budget_currency: str | None = None
    stats: dict | None = None
    modules: list[CarbonReportModuleRead] = []
    #: Set when the PATCH deferred its prefill to a ``simulator_plan_prefill``
    #: job (plan #2050 Track F4). ``None`` means there was nothing to wait
    #: for; otherwise the client polls this job before trusting the year's
    #: entries and stats.
    prefill_job_id: int | None = None

    class Config:
        from_attributes = True


class SimulatorPlanPrefillStatus(BaseModel):
    """Progress of a deferred plan prefill (plan #2050 Track F4)."""

    job_id: int
    #: True once the job reached its terminal state, whatever the outcome —
    #: the client stops polling and refetches the plan years.
    finished: bool
    #: Set only when finished: "success" | "warning" | "error".
    result: str | None = None
    status_message: str | None = None
