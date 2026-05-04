# codeql[py/unused-global-variable]
"""add computed to ingestion_method_enum

Revision ID: 707add_computed
Revises: 78a9e8951a27
Create Date: 2026-04-08 10:00:00.000000

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
revision: str = "707add_computed"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "78a9e8951a27"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Native PostgreSQL enum — ALTER TYPE ... ADD VALUE cannot run inside a
    # transaction in PostgreSQL < 12. PostgreSQL 12+ allows it, but the new
    # value is not visible until the transaction commits; that is acceptable here.
    op.execute("ALTER TYPE ingestion_method_enum ADD VALUE IF NOT EXISTS 'computed'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not support removing individual enum values.
    # A full enum-type recreation would be required; left as a no-op.
    pass
