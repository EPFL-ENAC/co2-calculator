from sqlmodel import Field, SQLModel

from app.models.user import RoleName


class UnitUser(SQLModel, table=True):
    """Association model linking Users to Units (many-to-many relationship)."""

    __tablename__ = "unit_users"
    unit_id: str | None = Field(default=None, foreign_key="units.id", primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", primary_key=True)
    role: str = Field(
        default=RoleName.CO2_USER_STD.value,
        nullable=False,
        index=True,
        description="User's role within the unit",
    )
