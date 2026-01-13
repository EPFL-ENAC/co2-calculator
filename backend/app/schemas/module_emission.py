"""Module emission schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModuleEmissionBase(BaseModel):
    """Base module emission schema."""

    module_id: int = Field(..., description="Source module ID")
    emission_type_id: int = Field(..., description="Emission type ID")
    factor_id: Optional[int] = Field(
        None, description="Generic factor used for calculation"
    )
    emission_factor_id: Optional[int] = Field(
        None, description="Emission factor used (e.g., electricity mix)"
    )
    kg_co2eq: float = Field(..., description="Computed emission in kgCO2eq")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Calculation metadata (annual_kwh, fte, etc.)",
    )
    formula_version: Optional[str] = Field(
        None, description="Version of calculation formula"
    )


class ModuleEmissionCreate(ModuleEmissionBase):
    """Schema for creating a module emission."""

    pass


class ModuleEmissionRead(ModuleEmissionBase):
    """Schema for reading a module emission."""

    id: int = Field(..., description="Emission ID")
    computed_at: datetime = Field(..., description="Computation timestamp")
    is_current: bool = Field(..., description="Whether this is the current value")

    class Config:
        """Pydantic config."""

        from_attributes = True


class ModuleEmissionResponse(ModuleEmissionRead):
    """API response schema for module emission."""

    emission_type_code: Optional[str] = Field(
        None, description="Emission type code (denormalized)"
    )
    emission_type_label: Optional[str] = Field(
        None, description="Emission type label (denormalized)"
    )


class FactorSnapshotResponse(BaseModel):
    """Factor snapshot from document_versions for audit trail."""

    factor_id: int = Field(..., description="Factor ID")
    version: int = Field(..., description="Factor version at calculation time")
    values: Dict[str, Any] = Field(..., description="Factor values snapshot")
    changed_at: datetime = Field(..., description="Version timestamp")


class ModuleEmissionWithHistory(ModuleEmissionResponse):
    """Module emission with factor history from document_versions.

    Replaces ModuleEmissionWithInputs - now uses document_versions for audit trail
    instead of module_emission_inputs table.
    """

    factor_snapshot: Optional[FactorSnapshotResponse] = Field(
        None, description="Factor values at computation time (from document_versions)"
    )
    emission_factor_snapshot: Optional[FactorSnapshotResponse] = Field(
        None,
        description="Emission factor values at computation time (from document_versions)",
    )


class EmissionCalculationRequest(BaseModel):
    """Request schema for triggering emission calculation."""

    module_id: int = Field(..., description="Module to calculate emissions for")
    force_recalculate: bool = Field(
        default=False, description="Force recalculation even if current exists"
    )


class EmissionCalculationResult(BaseModel):
    """Result of an emission calculation."""

    module_id: int = Field(..., description="Module ID")
    emissions: List[ModuleEmissionResponse] = Field(
        ..., description="Calculated emissions (1 for equipment, 4 for headcount)"
    )
    total_kg_co2eq: float = Field(..., description="Sum of all emissions")
    calculated_at: datetime = Field(..., description="Calculation timestamp")


class ModuleEmissionSummary(BaseModel):
    """Summary of emissions for a module or set of modules."""

    total_kg_co2eq: float = Field(..., description="Total emissions")
    total_t_co2eq: float = Field(..., description="Total emissions in tonnes")
    by_emission_type: Dict[str, float] = Field(
        default_factory=dict, description="Emissions grouped by type"
    )
    module_count: int = Field(..., description="Number of modules")
    emission_count: int = Field(..., description="Number of emission records")
