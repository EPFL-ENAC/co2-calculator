from datetime import datetime

from sqlalchemy import Column, DateTime, Index, text
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
    start_year: int | None = Field(default=None, nullable=True, index=True)
    end_year: int | None = Field(default=None, nullable=True, index=True)
    name: str | None = Field(default=None, nullable=True, index=True)
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
    created_by: int | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        description="User who created the project (set for Simulator Plan projects)",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Creation timestamp (set for Simulator Plan projects)",
    )


class CarbonProject(CarbonProjectBase, table=True):
    __tablename__ = "carbon_projects"

    __table_args__ = (
        # Two partial unique indexes. ddl_if gates both to Postgres: the
        # SQLite unit-test schema is intentionally unconstrained here.
        # One project per (unit_id, carbon_report_type) for Calculator /
        # Simulator_Explore; a unit may hold multiple Simulator_Plan
        # projects instead, unique per (unit_id, name) since the name is a
        # URL identifier.
        Index(
            "uq_carbon_projects_unit_type_nonplan",
            "unit_id",
            "carbon_report_type",
            unique=True,
            postgresql_where=text("carbon_report_type != 'Simulator_Plan'"),
        ).ddl_if(dialect="postgresql"),
        Index(
            "uq_carbon_projects_unit_plan_name",
            "unit_id",
            "name",
            unique=True,
            postgresql_where=text("carbon_report_type = 'Simulator_Plan'"),
        ).ddl_if(dialect="postgresql"),
    )

    id: int | None = Field(default=None, primary_key=True, index=True)
