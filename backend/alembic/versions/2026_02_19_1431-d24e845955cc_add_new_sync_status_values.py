# codeql[py/unused-global-variable]
"""add_new_sync_status_values

Revision ID: d24e845955cc
Revises: af2c356f7307
Create Date: 2026-02-19 14:31:22.704152

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
revision: str = "d24e845955cc"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "af2c356f7307"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum values to sync_status_enum
    op.execute("ALTER TYPE sync_status_enum ADD VALUE 'SKIPPED'")
    op.execute("ALTER TYPE sync_status_enum ADD VALUE 'RETRY_QUEUED'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # In a real downgrade scenario, we would need to:
    # 1. Create a new enum type without the new values
    # 2. Convert the column to use the new enum type
    # 3. Drop the old enum type
    # 4. Rename the new enum type to the original name
    # For simplicity in this migration, we'll leave the values in place
    pass
