"""Year configuration schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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


class SyncJobSummary(BaseModel):
    """Summary of the latest sync job for a submodule (read-only, not stored in DB)."""

    job_id: int = Field(..., description="Ingestion job ID")
    module_type_id: Optional[int] = Field(None, description="Module type ID")
    data_entry_type_id: Optional[int] = Field(None, description="Data entry type ID")
    year: Optional[int] = Field(None, description="Reference year")
    ingestion_method: int = Field(..., description="0=api, 1=csv, 2=manual")
    target_type: Optional[int] = Field(None, description="0=data_entries, 1=factors")
    state: Optional[int] = Field(None, description="0=NOT_STARTED..3=FINISHED")
    result: Optional[int] = Field(None, description="0=SUCCESS, 1=WARNING, 2=ERROR")
    status_message: Optional[str] = Field(None, description="Human-readable status")
    meta: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class SubmoduleConfig(BaseModel):
    """Configuration for a single data entry type (submodule)."""

    enabled: bool = Field(default=True, description="Whether this submodule is enabled")
    threshold: Optional[float] = Field(
        default=None,
        description="Fixed threshold in kgCO2eq (null if not set)",
    )

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: Optional[float]) -> Optional[float]:
        """Threshold must be >= 0 when set."""
        if v is not None and v < 0:
            raise ValueError("threshold must be >= 0")
        return v


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


class SubmoduleConfigResponse(SubmoduleConfig):
    """Submodule config enriched with latest sync job info (read-only)."""

    latest_job: Optional[SyncJobSummary] = Field(
        default=None,
        description="Latest sync job for this submodule (computed, not stored)",
    )


class ModuleConfigResponse(BaseModel):
    """Module config enriched with submodule job info (read-only)."""

    enabled: bool = Field(default=True)
    uncertainty_tag: UncertaintyTag = Field(default="medium")
    submodules: Dict[str, SubmoduleConfigResponse] = Field(default_factory=dict)


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

    @model_validator(mode="after")
    def validate_thresholds(self) -> "YearConfigurationUpdate":
        """Validate threshold values in modules config if provided."""
        if not self.config or "modules" not in self.config:
            return self
        modules = self.config["modules"]
        for module_key, module_val in modules.items():
            if not isinstance(module_val, dict):
                continue
            submodules = module_val.get("submodules", {})
            if not isinstance(submodules, dict):
                continue
            for sub_key, sub_val in submodules.items():
                if not isinstance(sub_val, dict):
                    continue
                threshold = sub_val.get("threshold")
                if threshold is not None and (
                    not isinstance(threshold, (int, float)) or threshold < 0
                ):
                    raise ValueError(
                        f"threshold for module {module_key} / submodule {sub_key} "
                        f"must be a number >= 0 or null, got {threshold}"
                    )
        return self


class YearConfigurationResponse(BaseModel):
    """Schema for year configuration response with enriched submodule data."""

    year: int
    is_started: bool
    is_reports_synced: bool
    config: Dict[str, Any]
    latest_jobs: List[SyncJobSummary] = Field(
        default_factory=list,
        description="All current ingestion jobs for this year",
    )
    updated_at: datetime

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""

    success: bool
    file: FileMetadata
    message: str
