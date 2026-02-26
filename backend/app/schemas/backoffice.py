"""Backoffice reporting schemas for API request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UnitReportingData(BaseModel):
    """Schema for individual unit reporting data."""

    unit_id: int = Field(..., alias="id")
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

    # URL or ID for the eye icon action
    view_url: Optional[str] = None

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
