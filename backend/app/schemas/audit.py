"""Audit log schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.audit import AuditChangeTypeEnum


class AuditLogEntry(BaseModel):
    """Single audit log entry returned by the API."""

    id: int
    entity_type: str
    entity_id: int
    version: int
    change_type: AuditChangeTypeEnum
    change_reason: Optional[str] = None
    changed_by: Optional[int] = None
    changed_by_display_name: Optional[str] = None
    changed_at: datetime
    handler_id: str
    handled_ids: List[str] = Field(default_factory=list)
    ip_address: str
    route_path: Optional[str] = None
    message_summary: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogDetail(AuditLogEntry):
    """Full audit log entry with snapshot and diff (for detail view)."""

    data_snapshot: Dict[str, Any] = Field(default_factory=dict)
    data_diff: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total: int


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    data: List[AuditLogEntry]
    pagination: PaginationMeta


class AuditStats(BaseModel):
    """Summary statistics for audit logs."""

    total_entries: int = 0
    creates: int = 0
    reads: int = 0
    updates: int = 0
    deletes: int = 0
