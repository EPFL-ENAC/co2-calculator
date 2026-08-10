from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.models.carbon_report import CarbonReportType


class CarbonProjectBase(SQLModel):
    """Carbon project model grouping carbon reports by type for a unit."""

    unit_id: int = Field(
        foreign_key="units.id",
        nullable=False,
        index=True,
        description="FK to units.id (integer)",
    )
    carbon_report_type: CarbonReportType = Field(
        sa_column=Column(
            SAEnum(
                CarbonReportType,
                name="carbon_report_type_enum",
                native_enum=True,
                values_callable=lambda x: [e.value for e in x],
            ),
            nullable=False,
        ),
        description="Project type: Calculator, Simulator_Explore, or Simulator_Plan",
    )
    start_year: Optional[int] = Field(default=None, nullable=True, index=True)
    end_year: Optional[int] = Field(default=None, nullable=True, index=True)
    name: Optional[str] = Field(default=None, nullable=True, index=True)
    is_viewable_by_unit_members: bool = Field(default=False, nullable=False)
    is_grant_proposal: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"server_default": "false"},
        description=(
            "Simulator Plan only: the plan carries a Project Grant section"
            " (a dedicated grant carbon report) in addition to its year reports"
        ),
    )
    created_by: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        description="User who created the project (set for Simulator Plan projects)",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Creation timestamp (set for Simulator Plan projects)",
    )


class CarbonProject(CarbonProjectBase, table=True):
    # Uniqueness is enforced by two partial indexes managed in the migration
    # (Postgres-only; the SQLite unit-test schema is intentionally
    # unconstrained):
    # - uq_carbon_projects_unit_type_nonplan: one project per (unit_id,
    #   carbon_report_type) for Calculator / Simulator_Explore
    # - uq_carbon_projects_unit_plan_name: unique (unit_id, name) among
    #   Simulator_Plan projects (the name is a URL identifier)
    __tablename__ = "carbon_projects"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
