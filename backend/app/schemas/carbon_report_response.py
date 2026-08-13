"""Equipment-related Pydantic schemas for API requests and responses."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SubmoduleSummary(BaseModel):
    """Summary statistics for a submodule."""

    total_items: int = Field(..., description="Number of equipment items")
    annual_fte: float | None = Field(
        None, description="Annual full-time equivalent (FTE) associated"
    )
    annual_consumption_kwh: float | None = Field(
        None, description="Total annual energy consumption"
    )
    total_kg_co2eq: float | None = Field(None, description="Total annual CO2 emissions")


class SubmoduleResponse[T: BaseModel](BaseModel):
    """Submodule data with items and summary."""

    id: int = Field(..., description="Submodule identifier")
    count: int = Field(..., description="Total number of items")
    items: Sequence[T] = Field(
        ..., description="Module items (equipment, headcount, or travel)"
    )
    summary: SubmoduleSummary = Field(..., description="Submodule summary")
    has_more: bool = Field(False, description="Whether more items are available")
    # #951: user/imported edit-rights for this submodule, keyed on row
    # provenance (each row already carries its own ``source``). None for
    # types the data-entry permission layer doesn't cover (planner, embodied
    # energy) — see app.core.data_entry_permissions.submodule_policies.
    data_entry_policies: dict[str, dict[str, object]] | None = Field(
        None, description="Edit rights per row provenance (user/imported)"
    )


class ModuleTotals(BaseModel):
    """Total statistics across all submodules."""

    # total_submodules: int = Field(..., description="Number of submodules")
    # total_items: int = Field(..., description="Total equipment count")
    total_annual_consumption_kwh: float | None = Field(
        None, description="Total annual energy consumption"
    )
    total_kg_co2eq: float | None = Field(
        None, description="Total annual CO2 emissions in kg CO2-eq"
    )
    total_tonnes_co2eq: float | None = Field(
        None, description="Total annual CO2 emissions in tonnes CO2-eq"
    )
    total_annual_fte: float | None = Field(
        None, description="Total full-time equivalent (FTE) associated"
    )


class ModuleResponse(BaseModel):
    """Complete module response with all submodules."""

    carbon_report_module_id: int | None = Field(
        None, description="Carbon report module ID"
    )
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")
    # submodules: Dict[int, SubmoduleResponse] = Field(
    #     ..., description="Submodule data keyed by data_entry_type_id (integer)"
    # )
    data_entry_types_total_items: dict[int, int] = Field(
        ..., description="Total items per data entry type ID"
    )
    stats: dict[str, float | None] | None = Field(None, description="Module statistics")
    totals: ModuleTotals = Field(..., description="Module totals")
    incomplete_new_equipment_count: int = Field(
        0,
        description=(
            "Equipment new vs the previous year that is still missing usage "
            "data (#259). Non-zero only for the Equipment module; blocks "
            "validation until zero."
        ),
    )


class TripLeg(BaseModel):
    """One professional-travel leg with geographic coordinates.

    Aggregation is left to the client: this is the raw row per DataEntry,
    not a per-route rollup. See ``GET /professional-travel/trips-map``.
    """

    mode: Literal["plane", "train"]
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float
    origin_name: str
    destination_name: str
    kg_co2eq: float
    number_of_trips: int = 1
    traveler_id: str = ""
    traveler_name: str = ""


class TripsMapResponse(BaseModel):
    """Flat list of trip legs for the professional-travel map.

    Legs whose origin or destination location could not be resolved to
    coordinates are dropped server-side; ``dropped_count`` lets the UI
    show "X trips not shown" if any.
    """

    legs: list[TripLeg]
    dropped_count: int = 0
