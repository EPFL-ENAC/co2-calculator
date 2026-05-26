"""Year configuration model for annual administrative settings."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import DateTime as SADateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import JSON, Field, SQLModel

from app.models.user import UserProvider


class YearConfigurationBase(SQLModel):
    """Base year configuration model."""

    is_started: bool = Field(
        default=False,
        description="If true, data entry is open for users for this year",
    )
    configuration_completed: Optional[datetime] = Field(
        default=None,
        sa_column=Column(SADateTime(timezone=True), nullable=True),
        description=(
            "Timestamp the unit_sync pipeline finished SUCCESSFULLY for "
            "this year/provider. NULL = not yet provisioned (uploads blocked)."
        ),
    )
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
        description="Deep configuration (thresholds, tags, goals) as JSON",
    )


class YearConfiguration(YearConfigurationBase, table=True):
    """Year configuration table, scoped by (year, provider).

    Each `UserProvider` has an independent row per year so TEST and ACCRED
    can be provisioned and opened independently in the same database.
    """

    __tablename__ = "year_configuration"

    year: int = Field(primary_key=True, description="The reference year")
    provider: UserProvider = Field(
        default=UserProvider.DEFAULT.value,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
            primary_key=True,
        ),
        description="Provider scope (accred, default, test)",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Last modification timestamp",
    )
