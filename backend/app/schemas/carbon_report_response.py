"""Equipment-related Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Dict, Optional, Sequence

from pydantic import BaseModel, Field

from app.models.headcount import HeadcountItemResponse
from app.models.professional_travel import ProfessionalTravelItemResponse
from app.schemas.equipment import EquipmentItemResponse


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

    id: int = Field(..., description="Submodule identifier")
    count: int = Field(..., description="Total number of items")
    items: Sequence[
        EquipmentItemResponse | HeadcountItemResponse | ProfessionalTravelItemResponse
    ] = Field(..., description="Module items (equipment, headcount, or travel)")
    summary: SubmoduleSummary = Field(..., description="Submodule summary")
    has_more: bool = Field(False, description="Whether more items are available")


class ModuleTotals(BaseModel):
    """Total statistics across all submodules."""

    # total_submodules: int = Field(..., description="Number of submodules")
    # total_items: int = Field(..., description="Total equipment count")
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

    carbon_report_module_id: Optional[int] = Field(
        None, description="Carbon report module ID"
    )
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")
    # submodules: Dict[int, SubmoduleResponse] = Field(
    #     ..., description="Submodule data keyed by data_entry_type_id (integer)"
    # )
    data_entry_types_total_items: Dict[int, int] = Field(
        ..., description="Total items per data entry type ID"
    )
    stats: Optional[dict[str, float]] = Field(None, description="Module statistics")
    totals: ModuleTotals = Field(..., description="Module totals")
