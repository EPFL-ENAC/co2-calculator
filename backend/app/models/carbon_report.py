from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.constants import ModuleStatus
from app.models.module_type import ModuleTypeEnum


class CarbonReportBase(SQLModel):
    """Base carbon report model."""

    year: int
    unit_id: int = Field(
        foreign_key="units.id",
        nullable=False,
        index=True,
        description="FK to units.id (integer)",
    )


class CarbonReport(CarbonReportBase, table=True):
    """
    Carbon report model representing an annual emissions report for a unit.

    A carbon report aggregates all emission data for a specific unit and year.
    """

    __tablename__ = "carbon_reports"
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique constraint for (year, unit_id)


class CarbonReportModuleBase(SQLModel):
    """Base carbon report module model."""

    # TODO: consider changing to ModuleTypeEnum
    module_type_id: int = Field(
        foreign_key="module_types.id",
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


class CarbonReportModule(CarbonReportModuleBase, table=True):
    """
    Carbon report module model representing a specific module within a carbon report.

    Each carbon report can have multiple modules (headcount, equipment, travel, etc.),
    each tracked separately for status and data entry.
    """

    __tablename__ = "carbon_report_modules"
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique constraint for (carbon_report_id, module_type_id) set in migration
