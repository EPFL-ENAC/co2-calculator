"""Simulator plan schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
    """Schema for renaming a simulator plan."""

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_plan_name(value)


class SimulatorPlanRead(BaseModel):
    """Schema for reading a simulator plan."""

    id: int
    unit_id: int
    name: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    creator_name: Optional[str] = None

    class Config:
        from_attributes = True
