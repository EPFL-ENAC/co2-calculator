# codeql[py/unused-global-variable]
"""add REDUCTION_OBJECTIVES to target_type_enum

Revision ID: 4226efc73854
Revises: 707add_computed
Create Date: 2026-04-16 09:18:59.871609

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
revision: str = "4226efc73854"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "707add_computed"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    """maybe try https://github.com/Pogchamp-company/alembic-postgresql-enum"""
    op.execute(
        "ALTER TYPE target_type_enum ADD VALUE IF NOT EXISTS 'REDUCTION_OBJECTIVES'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not support removing individual enum values.
    # A full enum-type recreation would be required; left as a no-op.
    pass
