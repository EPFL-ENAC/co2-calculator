"""Factor schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FactorBase(BaseModel):
    """Base factor schema."""

    factor_family: str = Field(
        ..., description="Factor family (power, headcount, flight, etc.)"
    )
    variant_type_id: Optional[int] = Field(
        None, description="Scope to specific variant"
    )
    classification: Dict[str, Any] = Field(
        default_factory=dict,
        description="Classification hierarchy (class, sub_class, etc.)",
    )
    values: Dict[str, float] = Field(
        default_factory=dict,
        description="Factor values (active_power_w, food_kg, etc.)",
    )
    unit: Optional[Dict[str, str]] = Field(None, description="Units for each value")
    source: Optional[str] = Field(None, description="Data source or reference")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    change_reason: Optional[str] = Field(
        None, description="Reason for this change (for audit trail)"
    )


class FactorCreate(FactorBase):
    """Schema for creating a factor."""

    version: int = Field(default=1, description="Version number")
    valid_from: Optional[datetime] = Field(None, description="Valid from date")
    valid_to: Optional[datetime] = Field(None, description="Valid to date")


class FactorUpdate(BaseModel):
    """Schema for updating a factor."""

    values: Optional[Dict[str, float]] = Field(None, description="New factor values")
    classification: Optional[Dict[str, Any]] = Field(
        None, description="New classification"
    )
    unit: Optional[Dict[str, str]] = Field(None, description="New units")
    source: Optional[str] = Field(None, description="New data source")
    meta: Optional[Dict[str, Any]] = Field(None, description="New metadata")
    change_reason: Optional[str] = Field(None, description="Reason for this update")


class FactorRead(FactorBase):
    """Schema for reading a factor."""

    id: int = Field(..., description="Factor ID")
    version: int = Field(..., description="Version number")
    valid_from: datetime = Field(..., description="Valid from date")
    valid_to: Optional[datetime] = Field(None, description="Valid to date")
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")

    class Config:
        """Pydantic config."""

        from_attributes = True


class FactorResponse(FactorRead):
    """API response schema for factor."""

    pass


class FactorLookupRequest(BaseModel):
    """Request schema for factor lookup."""

    factor_family: str = Field(..., description="Factor family to lookup")
    variant_type_id: Optional[int] = Field(None, description="Variant type filter")
    classification: Optional[Dict[str, Any]] = Field(
        None, description="Classification filter (partial match)"
    )


class PowerFactorValues(BaseModel):
    """Power factor values structure."""

    active_power_w: float = Field(..., description="Active power in Watts")
    standby_power_w: float = Field(..., description="Standby power in Watts")


class HeadcountFactorValues(BaseModel):
    """Headcount factor values structure."""

    food_kg: float = Field(..., description="Food emissions kgCO2eq/FTE/year")
    waste_kg: float = Field(..., description="Waste emissions kgCO2eq/FTE/year")
    transport_kg: float = Field(..., description="Transport emissions kgCO2eq/FTE/year")
    grey_energy_kg: float = Field(
        ..., description="Grey energy emissions kgCO2eq/FTE/year"
    )


class FactorVersionHistory(BaseModel):
    """Version history entry for a factor."""

    version: int = Field(..., description="Version number")
    change_type: str = Field(..., description="CREATE/UPDATE/DELETE/ROLLBACK")
    change_reason: Optional[str] = Field(None, description="Reason for change")
    changed_by: str = Field(..., description="User who made the change")
    changed_at: datetime = Field(..., description="Timestamp of change")
    data_diff: Optional[Dict[str, Any]] = Field(
        None, description="Diff from previous version"
    )


class RecalculationResponse(BaseModel):
    """Response for batch recalculation."""

    status: str = Field(..., description="Status: completed, partial, failed")
    factor_id: int = Field(..., description="Factor that triggered recalculation")
    total_modules: int = Field(..., description="Total modules affected")
    successful: int = Field(..., description="Successfully recalculated")
    failed: int = Field(..., description="Failed recalculations")
    failed_module_ids: List[int] = Field(
        default_factory=list, description="IDs of failed modules"
    )
    error_messages: List[str] = Field(
        default_factory=list, description="Error messages for failures"
    )
