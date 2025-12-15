"""Resource model for CO2 calculation resources."""

# from sqlalchemy import JSON, Column, Integer, String, Relationship

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


class UnitBase(SQLModel):
    """Base model for Units representing EPFL departments or organizational units."""

    name: str = Field(nullable=False, index=True)
    principal_user_id: str | None = Field(
        default=None,  # Removed: foreign_key="users.id"
        nullable=True,
        index=True,
        description="Principal user SCIPER",
    )
    principal_user_function: str | None = Field(
        default=None,
        nullable=True,
        description="Function/title of the principal user",
    )
    principal_user_name: str | None = Field(
        default=None,
        nullable=True,
        description="Name of the principal user",
    )
    principal_user_email: str | None = Field(
        default=None,
        nullable=True,
        description="Email of the principal user",
    )
    affiliations: list = Field(
        default=list,
        sa_column=Column(JSON),
        description="List of affiliations associated with the unit",
    )
    visibility: str = Field(
        default="private",
        nullable=False,
        description="Visibility level: public, private, or unit",
    )
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    created_by: Optional[str] = Field(default=None, index=True)
    updated_by: Optional[str] = Field(default=None, index=True)


class Unit(UnitBase, table=True):
    """
    Unit model representing CO2 calculation resources.

    Units can be filtered based on:
    - unit_id: EPFL unit/department
    - visibility: public, private, unit
    """

    __tablename__ = "units"
    id: str | None = Field(default=None, primary_key=True, index=True)
    cf: str | None = Field(
        default=None,
        nullable=True,
        description="other id associated with the unit",
    )
    provider: str = Field(
        nullable=False,
        description="Authentication provider (e.g. default, test, accred, ...)",
    )

    def __repr__(self) -> str:
        return f"<Unit {self.id}: {self.name}>"
