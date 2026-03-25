"""Backoffice reporting schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.constants import ModuleStatus


class UnitReportingData(BaseModel):
    """Schema for individual unit reporting data."""

    id: int
    unit_name: str  # Maps to "Unit" / "Unité" (Level 4 name)
    affiliation: str

    # Validation status: e.g., "3/7"
    validation_status: str

    # Source: ACCRED
    principal_user: str

    # Date of last module validation
    last_update: Optional[datetime]

    # Name of the module with the highest tCO2-eq
    highest_result_category: Optional[str]

    # Numeric value for the sum of emissions
    total_carbon_footprint: float = Field(..., description="Total tCO2-eq")

    # Aggregated FTE from headcount module data entries
    total_fte: Optional[float] = Field(None, description="Total FTE")

    # URL or ID for the eye icon action
    view_url: Optional[str] = None

    # Completion data for whole report
    completion: Optional[ModuleStatus] = None

    # Progress string from carbon_reports.completion_progress (e.g. "5/7")
    completion_progress: Optional[str] = None

    class Config:
        # Allows using the field names or the original aliases
        populate_by_name = True


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedUnitReportingData(BaseModel):
    """Paginated list of unit reporting data."""

    data: List[UnitReportingData]
    pagination: PaginationMeta
    emission_breakdown: Optional[Dict[str, Any]] = None
    validated_units_count: int = 0
    total_units_count: int = 0
