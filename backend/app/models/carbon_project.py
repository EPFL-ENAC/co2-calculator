from typing import Optional

from sqlalchemy import Column, UniqueConstraint
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


class CarbonProject(CarbonProjectBase, table=True):
    __tablename__ = "carbon_projects"
    __table_args__ = (
        UniqueConstraint(
            "unit_id",
            "carbon_report_type",
            name="uq_carbon_projects_unit_type",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
