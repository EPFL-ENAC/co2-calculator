"""Resource schemas for API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ResourceBase


class ResourceCreate(ResourceBase):
    """Schema for creating a new resource."""

    pass


class ResourceUpdate(ResourceBase):
    """Schema for updating a resource."""

    pass


class ResourceBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ResourceRead(BaseModel):
    """Schema for reading resource data."""

    id: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ResourceList(ResourceRead):
    """Schema for paginated resource list."""

    items: list[ResourceRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size
