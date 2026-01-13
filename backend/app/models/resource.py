"""Resource model for CO2 calculation resources."""

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, TIMESTAMP, Column, Field, SQLModel


class ResourceBase(SQLModel):
    # Resource metadata
    name: str = Field(nullable=False, index=True)
    description: str | None = Field(nullable=True)
    visibility: str = Field(
        default="private",
        nullable=False,
        description="Visibility level: public, private, unit",
    )

    # Resource data (flexible JSON structure)
    data: dict = Field(
        default_factory=dict,
        description="Resource-specific data",
        sa_column=Column(JSON),
    )
    meta: dict = Field(
        default_factory=dict,
        description="Additional metadata",
        sa_column=Column(JSON),
    )
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    created_by: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    updated_by: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    # Ownership and access control
    unit_id: int = Field(index=True, nullable=False, description="Unit ID (integer FK)")


class Resource(ResourceBase, table=True):
    """
    Resource model representing CO2 calculation resources.

    Resources can be filtered based on:
    - unit_id: EPFL unit/unit
    - owner_id: Resource owner
    - visibility: public, private, unit
    """

    __tablename__ = "resources"

    id: int | None = Field(primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<Resource {self.id}: {self.name}>"
