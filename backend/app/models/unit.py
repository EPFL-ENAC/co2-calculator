"""Resource model for CO2 calculation resources."""

from sqlalchemy import JSON, Column, Integer, String

from app.db import Base


class Unit(Base):
    """
    Unit model representing CO2 calculation resources.

    Units can be filtered based on:
    - unit_id: EPFL unit/department
    - visibility: public, private, unit
    """

    __tablename__ = "units"
    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, index=True)
    principal_user_id = Column(Integer, nullable=False, index=True)
    principal_user_name = Column(String, nullable=False)
    principal_user_function = Column(String, nullable=False)
    affiliations = Column(JSON, default=list)
    visibility = Column(
        String,
        default="private",
        nullable=False,
        comment="Visibility level: public, private, or unit",
    )

    def __repr__(self) -> str:
        return f"<Resource {self.id}: {self.name}>"
