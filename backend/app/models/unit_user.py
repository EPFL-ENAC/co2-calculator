from sqlmodel import Field, SQLModel


class UnitUser(SQLModel, table=True):
    """Association model linking Users to Units (many-to-many relationship)."""

    __tablename__ = "unit_users"
    unit_id: str | None = Field(default=None, foreign_key="units.id", primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", primary_key=True)
    role: str = Field(
        default="co2.user.std",
        nullable=False,
        index=True,
        description="User's role within the unit",
    )
