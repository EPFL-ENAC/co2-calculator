"""Resource model for CO2 calculation resources."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class Resource(Base):
    """
    Resource model representing CO2 calculation resources.

    Resources can be filtered based on:
    - unit_id: EPFL unit/department
    - owner_id: Resource owner
    - visibility: public, private, unit
    """

    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)

    # Resource metadata
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Ownership and access control
    unit_id = Column(
        String, index=True, nullable=False, comment="EPFL unit/department ID"
    )
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    visibility = Column(
        String,
        default="private",
        nullable=False,
        comment="Visibility level: public, private, unit",
    )

    # Resource data (flexible JSON structure)
    data = Column(JSONB, default=dict, comment="Resource-specific data")
    resource_metadata = Column(JSONB, default=dict, comment="Additional metadata")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="resources")

    def __repr__(self) -> str:
        return f"<Resource {self.id}: {self.name}>"
