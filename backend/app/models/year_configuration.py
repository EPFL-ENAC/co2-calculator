"""Year configuration model for annual administrative settings."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import DateTime as SADateTime
from sqlmodel import JSON, Field, SQLModel


class YearConfigurationBase(SQLModel):
    """Base year configuration model."""

    is_started: bool = Field(
        default=False,
        description="If true, data entry is open for users for this year",
    )
    # #1234-followup (Guilbert 2026-05-20): the `unit_sync` pipeline
    # provisions a year's carbon_reports + modules; uploads for the
    # year must NOT be accepted while that's running or before it ever
    # ran. ``configuration_completed`` is set by ``unit_sync_handler``
    # on SUCCESS (None until then). Dispatch gates on it.
    configuration_completed: Optional[datetime] = Field(
        default=None,
        sa_column=Column(SADateTime(timezone=True), nullable=True),
        description=(
            "Timestamp the unit_sync pipeline finished SUCCESSFULLY for "
            "this year. NULL = year not yet provisioned (uploads blocked)."
        ),
    )
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
        description="Deep configuration (thresholds, tags, goals) as JSON",
    )


class YearConfiguration(YearConfigurationBase, table=True):
    """Year configuration table for annual administrative settings.

    This table centralizes:
    - Annual administrative settings (is_started)
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
