"""Year configuration model for annual administrative settings."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


class YearConfigurationBase(SQLModel):
    """Base year configuration model."""

    is_started: bool = Field(
        default=False,
        description="If true, data entry is open for users for this year",
    )
    is_reports_synced: bool = Field(
        default=False,
        description="If true, carbon_reports have been initialized for this year",
    )
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
        description="Deep configuration (thresholds, tags, goals) as JSON",
    )


class YearConfiguration(YearConfigurationBase, table=True):
    """Year configuration table for annual administrative settings.

    This table centralizes:
    - Annual administrative settings (is_started, is_reports_synced)
    - Emission thresholds per module/submodule
    - Uncertainty levels
    - Institutional reduction goals

    The `config` JSONB column stores module configurations keyed by ModuleTypeEnum
    and DataEntryTypeEnum for O(1) lookup in the calculation engine.
    """

    __tablename__ = "year_configuration"

    year: int = Field(primary_key=True, description="The reference year")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Last modification timestamp",
    )

    id: Optional[int] = Field(default=None, primary_key=True)
