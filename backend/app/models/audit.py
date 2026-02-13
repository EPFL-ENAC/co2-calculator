"""Audit models for document versioning.

Defines a generic append-only `document_versions` table under the `audit` schema
for Postgres, with dialect-aware fallback for SQLite in tests/local dev.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import JSON, Field, SQLModel


class AuditChangeTypeEnum(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ROLLBACK = "ROLLBACK"
    TRANSFER = "TRANSFER"


# RENAME: audit -> document_versions
class AuditDocumentBase(SQLModel):
    """Base fields for versioned documents.

    This model is intentionally generic to support multiple entity types
    (e.g., modules, resources) via `entity_type` + `entity_id`.
    """

    entity_type: str = Field(index=True, description="Target table/entity name")
    entity_id: int = Field(index=True, description="Target entity primary key")

    version: int = Field(index=True, description="Monotonic version number")
    is_current: bool = Field(
        default=False, description="Whether this row is the current version"
    )

    # Store full snapshot and optional diff (JSON Patch or similar)
    data_snapshot: dict = Field(
        sa_column=Column(JSON), description="Canonical full JSON document"
    )
    data_diff: Optional[dict] = Field(
        default=None, sa_column=Column(JSON), description="Optional JSON diff"
    )

    # Audit metadata
    change_type: AuditChangeTypeEnum = Field(
        sa_column=Column(
            SAEnum(
                AuditChangeTypeEnum, name="audit_change_type_enum", native_enum=True
            ),
            nullable=False,
        ),
        description="CREATE/UPDATE/DELETE/ROLLBACK; enforced by DB check constraint",
    )
    change_reason: Optional[str] = Field(
        default=None, description="Optional human-readable reason for change"
    )
    changed_by: str = Field(description="Actor identifier (username/email)")
    changed_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of change (UTC)"
    )

    # Request context (mandatory audit fields)
    handler_id: str = Field(
        description="User provider code of who performed the action"
    )
    handled_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of user provider codes whose data was affected",
    )
    ip_address: str = Field(description="IP address of the requester machine")
    route_path: Optional[str] = Field(
        default=None, description="API route path that triggered the change"
    )
    route_payload: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Route payload/parameters that triggered the change",
    )

    # Integrity chain (hashes)
    previous_hash: Optional[str] = Field(
        default=None, description="Hash of previous version"
    )
    current_hash: str = Field(description="Hash of this version")


class AuditDocument(AuditDocumentBase, table=True):
    """Audit table storing versioned documents.

    Postgres placement: `audit_documents`.
    SQLite (tests/local): `audit_documents` in default schema.
    Indexes and constraints are created via Alembic migrations.
    Store one row per versioned document. a document being any entity that requires
    versioning (e.g., modules, resources). (CRUD operations are tracked via change_type
    and the actual data is stored as JSON snapshots/diffs.
    """

    __tablename__ = "audit_documents"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
