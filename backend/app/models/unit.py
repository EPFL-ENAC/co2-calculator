"""Unit model for CO2 calculation resources."""

from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


class UnitBase(SQLModel):
    """Base model for Units representing EPFL units or organizational units."""

    code: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Provider-assigned unit code (e.g., '10208' from accred)",
    )
    name: str = Field(nullable=False, index=True)
    principal_user_provider_code: str | None = Field(
        default=None,
        foreign_key="users.code",
        nullable=True,
        index=True,
        description="FK to users.code for the principal investigator",
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
    - code: Provider-assigned code (e.g., '10208')
    - name: Human-readable name (e.g., 'LCBM')
    """

    __tablename__ = "units"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    provider: str = Field(
        nullable=False,
        description="Sync source provider (accred, default, test)",
    )

    def __repr__(self) -> str:
        return f"<Unit {self.id} ({self.code}): {self.name}>"
