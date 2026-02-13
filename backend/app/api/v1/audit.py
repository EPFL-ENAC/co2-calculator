"""Audit log API endpoints.

Provides read-only access to the audit trail for service managers.
Supports filtering, pagination, sorting, and export.
"""

import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.user import User
from app.repositories.audit_repo import AuditDocumentRepository
from app.schemas.audit import (
    AuditLogDetail,
    AuditLogEntry,
    AuditLogListResponse,
    AuditStats,
    PaginationMeta,
)

logger = get_logger(__name__)
router = APIRouter()


async def _fetch_user_display_names(
    db: AsyncSession,
    provider_codes: list[str],
) -> dict[str, str]:
    if not provider_codes:
        return {}

    stmt = select(User.provider_code, User.display_name).where(
        col(User.provider_code).in_(provider_codes)
    )
    result = await db.exec(stmt)
    rows = result.all()
    return {
        provider_code: display_name
        for provider_code, display_name in rows
        if display_name
    }


def _build_message_summary(doc) -> Optional[str]:
    """Build a human-readable summary from an audit document."""
    parts = []
    ct = doc.change_type
    change_type = ct.value if hasattr(ct, "value") else str(ct)
    parts.append(change_type)
    parts.append(doc.entity_type)

    if doc.entity_id:
        parts.append(f"#{doc.entity_id}")

    if doc.change_reason:
        reason = doc.change_reason
        if len(reason) > 60:
            reason = reason[:57] + "..."
        parts.append(f"— {reason}")

    return " ".join(parts)


def _build_filters(
    user_id: Optional[int] = None,
    handler_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
    module: Optional[str] = None,
) -> dict[str, object]:
    """Construct a filters dict from query parameters."""
    filters: dict[str, object] = {}
    if user_id:
        filters["user_id"] = user_id
    if handler_id:
        filters["handler_id"] = handler_id
    if entity_type:
        filters["entity_type"] = entity_type
    if entity_id is not None:
        filters["entity_id"] = entity_id
    if action:
        filters["action"] = action
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    if search:
        filters["search"] = search
    if module:
        filters["module"] = module
    return filters


@router.get(
    "/activity",
    response_model=AuditLogListResponse,
)
async def list_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by actor"),
    handler_id: Optional[str] = Query(None, description="Filter by handler id"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    action: Optional[str] = Query(None, description="Filter by change type"),
    date_from: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    date_to: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    search: Optional[str] = Query(None, description="Free-text search"),
    module: Optional[str] = Query(None, description="Filter by module"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("changed_at"),
    sort_desc: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system.users", "edit")),
):
    """List audit log entries with filtering and pagination."""
    repo = AuditDocumentRepository(db)
    filters = _build_filters(
        user_id=user_id,
        handler_id=handler_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        search=search,
        module=module,
    )

    docs, total = await repo.query(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )

    display_names = await _fetch_user_display_names(
        db,
        [doc.handler_id for doc in docs if doc.handler_id],
    )

    entries = []
    for doc in docs:
        if doc.id is None:
            continue
        entries.append(
            AuditLogEntry(
                id=doc.id,
                entity_type=doc.entity_type,
                entity_id=doc.entity_id,
                version=doc.version,
                change_type=doc.change_type,
                change_reason=doc.change_reason,
                changed_by=doc.changed_by,
                changed_by_display_name=display_names.get(doc.handler_id),
                changed_at=doc.changed_at,
                handler_id=doc.handler_id,
                handled_ids=doc.handled_ids or [],
                ip_address=doc.ip_address,
                route_path=doc.route_path,
                message_summary=_build_message_summary(doc),
            )
        )

    return AuditLogListResponse(
        data=entries,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
        ),
    )


@router.get(
    "/stats",
    response_model=AuditStats,
)
async def get_audit_stats(
    user_id: Optional[int] = Query(None),
    handler_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system.users", "edit")),
):
    """Get summary statistics for audit logs, respecting current filters."""
    repo = AuditDocumentRepository(db)
    filters = _build_filters(
        user_id=user_id,
        handler_id=handler_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        search=search,
        module=module,
    )

    counts = await repo.count_by_change_type(filters)

    total = sum(counts.values())

    return AuditStats(
        total_entries=total,
        creates=counts.get("CREATE", 0),
        reads=counts.get("READ", 0),
        updates=counts.get("UPDATE", 0),
        deletes=counts.get("DELETE", 0),
    )


@router.get(
    "/activity/{log_id}",
    response_model=AuditLogDetail,
)
async def get_audit_log_detail(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system.users", "edit")),
):
    """Get full details of a single audit log entry."""
    repo = AuditDocumentRepository(db)
    doc = await repo.get_by_id(log_id)

    if doc is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log entry {log_id} not found",
        )

    display_names = await _fetch_user_display_names(
        db,
        [doc.handler_id] if doc.handler_id else [],
    )

    if doc.id is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit log entry has no id",
        )

    return AuditLogDetail(
        id=doc.id,
        entity_type=doc.entity_type,
        entity_id=doc.entity_id,
        version=doc.version,
        change_type=doc.change_type,
        change_reason=doc.change_reason,
        changed_by=doc.changed_by,
        changed_by_display_name=display_names.get(doc.handler_id),
        changed_at=doc.changed_at,
        handler_id=doc.handler_id,
        handled_ids=doc.handled_ids or [],
        ip_address=doc.ip_address,
        route_path=doc.route_path,
        message_summary=_build_message_summary(doc),
        data_snapshot=doc.data_snapshot or {},
        data_diff=doc.data_diff,
    )


@router.get("/export")
async def export_audit_logs(
    user_id: Optional[int] = Query(None),
    handler_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    format: str = Query("csv", description="Export format: csv or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system.users", "edit")),
):
    """Export audit logs as CSV or JSON file download."""
    repo = AuditDocumentRepository(db)
    filters = _build_filters(
        user_id=user_id,
        handler_id=handler_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        search=search,
        module=module,
    )

    # Fetch all matching records (cap at 10000 for safety)
    docs, total = await repo.query(
        filters=filters,
        page=1,
        page_size=10000,
        sort_by="changed_at",
        sort_desc=True,
    )

    today = datetime.utcnow().strftime("%Y-%m-%d")

    if format == "json":
        # JSON export
        export_data = [
            {
                "id": doc.id,
                "entity_type": doc.entity_type,
                "entity_id": doc.entity_id,
                "version": doc.version,
                "change_type": (
                    doc.change_type.value
                    if hasattr(doc.change_type, "value")
                    else str(doc.change_type)
                ),
                "change_reason": doc.change_reason,
                "changed_by": doc.changed_by,
                "changed_at": doc.changed_at.isoformat() if doc.changed_at else None,
                "handler_id": doc.handler_id,
                "handled_ids": doc.handled_ids or [],
                "ip_address": doc.ip_address,
                "route_path": doc.route_path,
                "data_snapshot": doc.data_snapshot,
                "data_diff": doc.data_diff,
            }
            for doc in docs
        ]

        content = json.dumps(export_data, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="audit_export_{today}.json"'
                ),
            },
        )
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "entity_type",
                "entity_id",
                "version",
                "change_type",
                "change_reason",
                "changed_by",
                "changed_at",
                "handler_id",
                "handled_ids",
                "ip_address",
                "route_path",
            ]
        )

        for doc in docs:
            ct = doc.change_type
            change_type = ct.value if hasattr(ct, "value") else str(ct)
            writer.writerow(
                [
                    doc.id,
                    doc.entity_type,
                    doc.entity_id,
                    doc.version,
                    change_type,
                    doc.change_reason or "",
                    doc.changed_by,
                    doc.changed_at.isoformat() if doc.changed_at else "",
                    doc.handler_id,
                    ";".join(doc.handled_ids) if doc.handled_ids else "",
                    doc.ip_address,
                    doc.route_path or "",
                ]
            )

        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="audit_export_{today}.csv"'
                ),
            },
        )
