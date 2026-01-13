"""Equipment-related Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Dict, Optional, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import get_settings
from app.models.headcount import HeadcountItemResponse

settings = get_settings()


class EquipmentItemResponse(BaseModel):
    """Equipment item with calculated emissions (matches mock data format)."""

    id: int = Field(..., description="Equipment ID")
    name: str = Field(..., description="Equipment name")
    category: str = Field(..., description="Source category")
    submodule: str = Field(..., description="Submodule grouping")
    equipment_class: str = Field(..., description="Equipment class")
    sub_class: Optional[str] = Field(None, description="Equipment sub-class")
    act_usage: float = Field(..., description="Active usage hours per week")
    pas_usage: float = Field(..., description="Passive usage hours per week")
    standby_power_w: Optional[float] = Field(None, description="Standby power in Watts")
    active_power_w: Optional[float] = Field(None, description="Active power in Watts")
    status: str = Field(..., description="Equipment status")
    kg_co2eq: float = Field(..., description="Annual CO2 emissions in kg CO2-eq")
    t_co2eq: float = Field(
        ..., description="Annual CO2 emissions in tonnes CO2-eq (rounded up)"
    )
    annual_kwh: float = Field(..., description="Annual energy consumption in kWh")

    class Config:
        """Pydantic config."""

        populate_by_name = True


class SubmoduleSummary(BaseModel):
    """Summary statistics for a submodule."""

    total_items: int = Field(..., description="Number of equipment items")
    annual_fte: Optional[float] = Field(
        None, description="Annual full-time equivalent (FTE) associated"
    )
    annual_consumption_kwh: Optional[float] = Field(
        None, description="Total annual energy consumption"
    )
    total_kg_co2eq: Optional[float] = Field(
        None, description="Total annual CO2 emissions"
    )


class SubmoduleResponse(BaseModel):
    """Submodule data with items and summary."""

    id: str = Field(..., description="Submodule identifier")
    name: str = Field(..., description="Submodule display name")
    count: int = Field(..., description="Total number of items")
    items: Sequence[EquipmentItemResponse | HeadcountItemResponse] = Field(
        ..., description="Equipment items"
    )
    summary: SubmoduleSummary = Field(..., description="Submodule summary")
    has_more: bool = Field(False, description="Whether more items are available")


class ModuleTotals(BaseModel):
    """Total statistics across all submodules."""

    total_submodules: int = Field(..., description="Number of submodules")
    total_items: int = Field(..., description="Total equipment count")
    total_annual_consumption_kwh: Optional[float] = Field(
        None, description="Total annual energy consumption"
    )
    total_kg_co2eq: Optional[float] = Field(
        None, description="Total annual CO2 emissions in kg CO2-eq"
    )
    total_tonnes_co2eq: Optional[float] = Field(
        None, description="Total annual CO2 emissions in tonnes CO2-eq"
    )
    total_annual_fte: Optional[float] = Field(
        None, description="Total full-time equivalent (FTE) associated"
    )


class ModuleResponse(BaseModel):
    """Complete module response with all submodules."""

    module_type: str = Field(..., description="Module type identifier")
    unit: str = Field(..., description="Unit of measurement")
    year: int = Field(..., description="Data year")
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")
    submodules: Dict[str, SubmoduleResponse] = Field(
        ..., description="Submodule data keyed by submodule ID"
    )
    stats: Optional[dict[str, float]] = Field(None, description="Module statistics")
    totals: ModuleTotals = Field(..., description="Module totals")


class EquipmentFilters(BaseModel):
    """Filters for equipment queries."""

    unit_id: Optional[str] = Field(None, description="Filter by unit ID")
    status: Optional[str] = Field("In service", description="Filter by status")
    submodule: Optional[str] = Field(None, description="Filter by submodule")
    service_date_from: Optional[datetime] = Field(
        None, description="Filter by service date (from)"
    )
    service_date_to: Optional[datetime] = Field(
        None, description="Filter by service date (to)"
    )


class EquipmentCreateRequest(BaseModel):
    """Request schema for creating new equipment."""

    unit_id: int = Field(..., description="Unit ID (e.g., '10208')")
    cost_center: Optional[str] = Field(
        None, description="Cost center code (defaults to unit_id if not provided)"
    )
    name: str = Field(..., min_length=1, max_length=500, description="Equipment name")
    category: str = Field(..., description="Equipment category")
    submodule: str = Field(
        ..., description="Submodule grouping: 'scientific', 'it', or 'other'"
    )
    equipment_class: str = Field(..., description="Equipment class")
    sub_class: Optional[str] = Field(None, description="Equipment sub-class")
    act_usage: Optional[float] = Field(
        None,
        ge=0,
        le=settings.HOURS_PER_WEEK,
        description=f"Active usage hours per week (0-{settings.HOURS_PER_WEEK})",
    )
    pas_usage: Optional[float] = Field(
        None,
        ge=0,
        le=settings.HOURS_PER_WEEK,
        description=f"Passive usage hours per week (0-{settings.HOURS_PER_WEEK})",
    )

    power_factor_id: Optional[int] = Field(
        None, description="Reference to power factor lookup"
    )
    status: str = Field(default="In service", description="Equipment status")
    service_date: Optional[datetime] = Field(None, description="Date put into service")
    cost_center_description: Optional[str] = Field(
        None, description="Cost center description"
    )
    metadata: Optional[Dict] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("submodule")
    @classmethod
    def validate_submodule(cls, v: str) -> str:
        """Validate submodule is one of the allowed values."""
        allowed = {"scientific", "it", "other"}
        if v not in allowed:
            raise ValueError(f"submodule must be one of: {allowed}")
        return v

    @model_validator(mode="after")
    def validate_total_usage(self):
        """Validate total usage doesn't exceed
        {settings.HOURS_PER_WEEK} hours per week."""
        if self.act_usage is not None and self.pas_usage is not None:
            total = self.act_usage + self.pas_usage
            if total > settings.HOURS_PER_WEEK:
                raise ValueError(
                    f"Total usage (act_usage + pas_usage) cannot exceed "
                    f"{settings.HOURS_PER_WEEK} hours per week. Got: {total}"
                )
        return self

    class Config:
        """Pydantic config."""

        populate_by_name = True


class EquipmentUpdateRequest(BaseModel):
    """Request schema for updating existing equipment."""

    cost_center: Optional[str] = Field(None, description="Cost center code")
    name: Optional[str] = Field(
        None, min_length=1, max_length=500, description="Equipment name"
    )
    category: Optional[str] = Field(None, description="Equipment category")
    submodule: Optional[str] = Field(
        None, description="Submodule grouping: 'scientific', 'it', or 'other'"
    )
    equipment_class: Optional[str] = Field(None, description="Equipment class")
    sub_class: Optional[str] = Field(None, description="Equipment sub-class")
    act_usage: Optional[float] = Field(
        None,
        ge=0,
        le=settings.HOURS_PER_WEEK,
        description=f"Active usage hours per week (0-{settings.HOURS_PER_WEEK})",
    )
    pas_usage: Optional[float] = Field(
        None,
        ge=0,
        le=settings.HOURS_PER_WEEK,
        description=f"Passive usage hours per week (0-{settings.HOURS_PER_WEEK})",
    )
    power_factor_id: Optional[int] = Field(
        None, description="Reference to power factor lookup"
    )
    status: Optional[str] = Field(None, description="Equipment status")
    service_date: Optional[datetime] = Field(None, description="Date put into service")
    cost_center_description: Optional[str] = Field(
        None, description="French description"
    )
    metadata: Optional[Dict] = Field(None, description="Additional metadata")

    @field_validator("submodule")
    @classmethod
    def validate_submodule(cls, v: Optional[str]) -> Optional[str]:
        """Validate submodule is one of the allowed values."""
        if v is not None:
            allowed = {"scientific", "it", "other"}
            if v not in allowed:
                raise ValueError(f"submodule must be one of: {allowed}")
        return v

    @model_validator(mode="after")
    def validate_total_usage(self):
        """Validate total usage doesn't exceed
        settings.HOURS_PER_WEEK hours per week."""
        if self.act_usage is not None and self.pas_usage is not None:
            total = self.act_usage + self.pas_usage
            if total > settings.HOURS_PER_WEEK:
                raise ValueError(
                    f"Total usage (act_usage + pas_usage) cannot exceed "
                    f"{settings.HOURS_PER_WEEK} hours per week. Got: {total}"
                )
        return self

    class Config:
        """Pydantic config."""

        populate_by_name = True


class EquipmentDetailResponse(BaseModel):
    """Detailed equipment response including ID and metadata."""

    id: int = Field(..., description="Equipment ID")
    cost_center: str = Field(..., description="Cost center code")
    unit_id: int = Field(..., description="Unit ID")
    name: str = Field(..., description="Equipment name")
    category: str = Field(..., description="Equipment category")
    submodule: str = Field(..., description="Submodule grouping")
    equipment_class: str = Field(..., description="Equipment class")
    sub_class: Optional[str] = Field(None, description="Equipment sub-class")
    act_usage: Optional[float] = Field(None, description="Active usage hours per week")
    pas_usage: Optional[float] = Field(None, description="Passive usage hours per week")

    power_factor_id: Optional[int] = Field(None, description="Power factor reference")
    status: str = Field(..., description="Equipment status")
    service_date: Optional[datetime] = Field(None, description="Date put into service")
    cost_center_description: Optional[str] = Field(
        None, description="French description"
    )
    meta: Optional[Dict] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")

    class Config:
        """Pydantic config."""

        populate_by_name = True
        from_attributes = True
