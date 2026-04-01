"""Year configuration schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Type definitions
UncertaintyTag = Literal["low", "medium", "high", "none"]
FileCategory = Literal["footprint", "population", "scenarios"]


class FileMetadata(BaseModel):
    """Metadata for uploaded files."""

    path: str = Field(..., description="Storage path for the file")
    filename: str = Field(..., description="Original filename")
    uploaded_at: str = Field(..., description="Upload timestamp in ISO format")


class ReductionObjectiveGoal(BaseModel):
    """Institutional reduction goal configuration."""

    target_year: int = Field(..., description="Target year for reduction")
    reduction_percentage: float = Field(
        ...,
        ge=0,
        le=1,
        description="Reduction percentage as decimal (e.g., 0.4 for 40%)",
    )
    reference_year: int = Field(
        ..., description="Reference year to calculate reduction from"
    )

    @field_validator("target_year")
    @classmethod
    def validate_target_year(cls, v: int, info) -> int:
        """Validate target_year is greater than configuration year."""
        # Note: We can't access 'year' here directly, validation happens in service
        return v


class ReductionObjectives(BaseModel):
    """Reduction objectives configuration."""

    files: Dict[
        Literal["institutional_footprint", "population_projections", "unit_scenarios"],
        Optional[FileMetadata],
    ] = Field(
        default_factory=lambda: {  # type: ignore
            "institutional_footprint": None,
            "population_projections": None,
            "unit_scenarios": None,
        },
        description="File metadata for reduction objective references",
    )
    goals: List[ReductionObjectiveGoal] = Field(
        default_factory=list,
        description="List of institutional reduction goals",
    )


class SubmoduleConfig(BaseModel):
    """Configuration for a single data entry type (submodule)."""

    enabled: bool = Field(default=True, description="Whether this submodule is enabled")
    threshold: Optional[float] = Field(
        default=None,
        description="Fixed threshold in kgCO2eq (null if not set)",
    )


class ModuleConfig(BaseModel):
    """Configuration for a module type."""

    enabled: bool = Field(default=True, description="Whether this module is enabled")
    uncertainty_tag: UncertaintyTag = Field(
        default="medium", description="Uncertainty level for the module"
    )
    submodules: Dict[str, SubmoduleConfig] = Field(
        default_factory=dict,
        description="Configuration for each data entry type under this module",
    )


class YearConfigJSON(BaseModel):
    """Complete year configuration JSON structure."""

    modules: Dict[str, ModuleConfig] = Field(
        default_factory=dict,
        description="Module configurations keyed by module_type_id (as string)",
    )
    reduction_objectives: Optional[ReductionObjectives] = Field(
        default=None,
        description="Institutional reduction objectives and file references",
    )


class YearConfigurationBase(BaseModel):
    """Base schema for year configuration."""

    is_started: bool = Field(
        default=False,
        description="If true, data entry is open for users for this year",
    )
    is_reports_synced: bool = Field(
        default=False,
        description="If true, carbon_reports have been initialized for this year",
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deep configuration (thresholds, tags, goals) as JSON",
    )


class YearConfigurationCreate(YearConfigurationBase):
    """Schema for creating/updating year configuration."""

    pass


class YearConfigurationUpdate(BaseModel):
    """Schema for partial update of year configuration."""

    is_started: Optional[bool] = None
    is_reports_synced: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class YearConfigurationResponse(BaseModel):
    """Schema for year configuration response."""

    year: int
    is_started: bool
    is_reports_synced: bool
    config: Dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""

    success: bool
    file: FileMetadata
    message: str
