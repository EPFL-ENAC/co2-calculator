"""Backoffice reporting schemas for API request/response validation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

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
    last_update: Optional[datetime] = None

    # Name of the module with the highest tCO2-eq
    highest_result_category: Optional[str] = None

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

    @field_serializer("last_update")
    def serialize_last_update(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    class Config:
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
    # Merged per-report stats across the filtered units. The frontend reshapes
    # this into the emission/IT breakdown rows the reporting charts consume.
    stats: Optional[Dict[str, Any]] = None
    validated_units_count: int = 0
    in_progress_units_count: int = 0
    not_started_units_count: int = 0
    total_units_count: int = 0
    module_status_counts: Optional[Dict[int, int]] = None


class PaginatedBackofficeFactors(BaseModel):
    """Paginated factor rows for the backoffice factor viewer (#1491).

    Rows are the handler's response DTO dump plus ``year`` and
    ``last_seen_job_id`` (so an operator can spot rows the latest
    upload did not assert) — shape varies per data entry type, hence
    the open dict.
    """

    data: List[Dict[str, Any]]
    pagination: PaginationMeta


class BulkDeleteResponse(BaseModel):
    """Result of a backoffice bulk delete (#1491).

    ``recalc_job_id``/``recalc_pipeline_id`` reference the emission
    recalculation dispatched to keep emissions and stat buckets
    consistent after the delete; None when nothing was deleted.
    """

    deleted: int
    recalc_job_id: Optional[int] = None
    recalc_pipeline_id: Optional[str] = None
