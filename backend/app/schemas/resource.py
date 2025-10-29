"""Resource schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ResourceBase(BaseModel):
    """Base resource schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    unit_id: str = Field(..., description="EPFL unit/department ID")
    visibility: str = Field(
        default="private",
        pattern="^(public|private|unit)$",
        description="Visibility level: public, private, or unit",
    )
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResourceCreate(ResourceBase):
    """Schema for creating a new resource."""

    pass


class ResourceUpdate(BaseModel):
    """Schema for updating a resource."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    visibility: Optional[str] = Field(None, pattern="^(public|private|unit)$")
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ResourceRead(ResourceBase):
    """Schema for reading resource data."""

    id: int
    owner_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        # Map resource_metadata from DB to metadata in API
        populate_by_name = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Custom validation to map resource_metadata to metadata."""
        if hasattr(obj, "resource_metadata"):
            obj.metadata = obj.resource_metadata
        return super().model_validate(obj, **kwargs)


class ResourceList(BaseModel):
    """Schema for paginated resource list."""

    items: list[ResourceRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size
