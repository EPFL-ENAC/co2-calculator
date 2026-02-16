# codeql[py/unused-global-variable]
"""add audit query indexes

Revision ID: a1b2c3d4e5f6
Revises: 5f751eaf2cfa
Create Date: 2026-02-13 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "5f751eaf2cfa"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Add indexes for audit log query performance."""
    op.create_index(
        "ix_audit_documents_changed_at",
        "audit_documents",
        ["changed_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_documents_changed_by",
        "audit_documents",
        ["changed_by"],
        unique=False,
    )
    op.create_index(
        "ix_audit_documents_change_type",
        "audit_documents",
        ["change_type"],
        unique=False,
    )
    op.create_index(
        "ix_audit_documents_composite",
        "audit_documents",
        ["entity_type", "entity_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove audit query indexes."""
    op.drop_index("ix_audit_documents_composite", table_name="audit_documents")
    op.drop_index("ix_audit_documents_change_type", table_name="audit_documents")
    op.drop_index("ix_audit_documents_changed_by", table_name="audit_documents")
    op.drop_index("ix_audit_documents_changed_at", table_name="audit_documents")
