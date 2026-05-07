from enum import Enum
from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.core.constants import ModuleStatus


class CarbonReportType(str, Enum):
    CALCULATOR = "Calculator"
    SIMULATOR_EXPLORE = "Simulator_Explore"
    SIMULATOR_PLAN = "Simulator_Plan"


class CarbonReportBase(SQLModel):
    """Base carbon report model."""

    year: int = Field(
        nullable=False,
        description=(
            "Report year (always set; for Simulator Explore, equals the reference year)"
        ),
    )
    reference_year: Optional[int] = Field(
        default=None,
        nullable=True,
        description=(
            "Optional reference year"
            " (reserved for Simulator Plan to track baseline year)"
        ),
    )
    unit_id: int = Field(
        foreign_key="units.id",
        nullable=False,
        index=True,
        description="FK to units.id (integer)",
    )
    carbon_project_id: Optional[int] = Field(
        default=None,
        foreign_key="carbon_projects.id",
        nullable=True,
        index=True,
        description="FK to carbon_projects.id — every report may belong to a project",
    )
    last_updated: Optional[int] = Field(
        default=None,
        description=(
            "Timestamp of last update (epoch seconds)"
            " - used for concurrency control and freshness checks"
            " - updated automatically on data changes in any child module"
            " - can be null if never updated since creation"
        ),
    )
    completion_progress: Optional[str] = Field(
        default=None,
        description=(
            "String representation of completion progress (e.g., '5/7')"
            " - shows how many modules are completed vs total modules"
            " - updated automatically when child module status changes"
        ),
    )
    overall_status: int = Field(
        default=ModuleStatus.NOT_STARTED,
        description=(
            "Overall status inferred from child modules:"
            " NOT_STARTED (0) if no modules started,"
            " IN_PROGRESS (1) if some but not all modules completed,"
            " VALIDATED (2) if all modules are validated"
        ),
    )
    stats: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description=(
            "Optional JSON field to store pre-calculated statistics for the report"
            " - aggregates stats from all child CarbonReportModule records"
            " - includes scope totals, by_emission_type, by_additional_value, "
            "computed_at, and entry_count"
            " - helps optimize frontend performance by avoiding on-the-fly calculations"
            ".e.g: { scope1: kg, scope2: kg, scope3: kg, total: kg, "
            "by_emission_type: { emission_type_id: kg, ... }, "
            "by_additional_value: { emission_type_id: value, ... }, "
            "computed_at: iso_timestamp, entry_count: int }"
        ),
    )


class CarbonReport(CarbonReportBase, table=True):
    """
    Carbon report model representing an annual emissions report for a unit.

    A carbon report aggregates all emission data for a specific unit and year.
    """

    __tablename__ = "carbon_reports"
    __table_args__ = (
        UniqueConstraint(
            "carbon_project_id",
            "year",
            name="uq_carbon_reports_project_year",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)


class CarbonReportModuleBase(SQLModel):
    """Base carbon report module model."""

    # TODO: consider changing to ModuleTypeEnum with setter getter conversion
    module_type_id: int = Field(
        nullable=False,
        index=True,
        description="Reference to module type classification",
    )
    status: int = Field(
        default=ModuleStatus.NOT_STARTED,
        description="Module status: 0=not_started, 1=in_progress, 2=validated",
    )
    carbon_report_id: int = Field(
        foreign_key="carbon_reports.id",
        index=True,
        description="Reference to parent carbon report",
    )
    last_updated: Optional[int] = Field(
        default=None,
        description=(
            "Timestamp of last update (epoch seconds)"
            " - used for concurrency control and freshness checks"
            " - updated automatically on data changes in the module"
            " - can be null if never updated since creation"
        ),
    )
    stats: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description=(
            "Optional JSON field to store pre-calculated statistics for the module"
            " - can include counts, sums, or other aggregates relevant to the module"
            " - helps optimize frontend performance by avoiding on-the-fly calculations"
            " - should be kg_co2eq totals and for each emission_type_id in the module,"
            "to support frontend breakdowns by emission type"
            " - may include by_additional_value totals for physical quantities"
            ".e.g: { 1: kg_co2eq, 2: kg_co2eq, 'total': kg_co2eq_total }"
        ),
    )


class CarbonReportModule(CarbonReportModuleBase, table=True):
    """
    Carbon report module model representing a specific module within a carbon report.

    Each carbon report can have multiple modules (headcount, equipment, travel, etc.),
    each tracked separately for status and data entry.
    """

    __tablename__ = "carbon_report_modules"
    __table_args__ = (
        Index(
            "idx_crm_report_type_status", "carbon_report_id", "module_type_id", "status"
        ),
        UniqueConstraint(
            "carbon_report_id", "module_type_id", name="uq_carbon_report_module"
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)


class CarbonReportModuleRead(CarbonReportModuleBase):
    """The DTO used for reading data. ID is strictly an int."""

    id: int
