"""Unit model for CO2 calculation."""

from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlmodel import JSON, Column, Field, SQLModel

from app.models.user import UserProvider


class UnitBase(SQLModel):
    """Base model for Units representing EPFL units or organizational units."""

    provider_code: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Provider-assigned unit code (e.g., '10208' from accred)",
    )
    name: str = Field(nullable=False, index=True)
    principal_user_provider_code: str | None = Field(
        default=None,
        foreign_key="users.provider_code",
        nullable=True,
        index=True,
        description="FK to users.provider_code for the principal investigator",
    )
    cost_centers: list = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of cost center codes (Finance IDs, e.g., ['C1348', 'C1349'])",
    )
    affiliations: list = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of affiliations (e.g., ['SB', 'ISIC'])",
    )


class Unit(UnitBase, table=True):
    """
    Unit model representing organizational units for CO2 reporting.

    Synced from third-party providers (accred, default, test).

    Units can be filtered based on:
    - id: Internal integer PK
    - provider_code: Provider-assigned code (e.g., '10208')
    - name: Human-readable name (e.g., 'LCBM')
    """

    __tablename__ = "units"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    provider: UserProvider = Field(
        default=UserProvider.DEFAULT.value,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
        ),
        description="Sync source provider (accred, default, test)",
    )

    def __repr__(self) -> str:
        return f"<Unit {self.id} ({self.provider_code}): {self.name}>"
