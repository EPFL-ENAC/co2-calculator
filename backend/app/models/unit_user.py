"""Unit-User association model."""

from typing import Optional

from sqlmodel import Field, SQLModel


class UnitUser(SQLModel, table=True):
    """Association model linking Users to Units (many-to-many relationship)."""

    __tablename__ = "unit_users"
    id: Optional[int] = Field(default=None, primary_key=True)
    unit_id: int = Field(foreign_key="units.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    role: str = Field(
        default="co2.user.std",
        nullable=False,
        index=True,
        description="User's role within the unit",
    )
