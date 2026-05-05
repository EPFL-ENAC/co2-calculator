# codeql[py/unused-global-variable]
"""add REFERENCE_DATA to target_type_enum

Revision ID: c2d4e6f8a012
Revises: b1f0a2c3d4e5
Create Date: 2026-05-01 16:00:00.000000

The Python ``TargetType`` enum has had ``REFERENCE_DATA = 3`` for a
while, but the Postgres ``target_type_enum`` type was never extended
with the matching label.  The Plan 310B unit-sync job tries to insert
``target_type='REFERENCE_DATA'`` and trips
``invalid input value for enum target_type_enum``.

Mirror the precedent set by 4226efc73854 (REDUCTION_OBJECTIVES) — a
plain ``ALTER TYPE ... ADD VALUE IF NOT EXISTS``.
"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "c2d4e6f8a012"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "b1f0a2c3d4e5"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE target_type_enum ADD VALUE IF NOT EXISTS 'REFERENCE_DATA'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL does not support removing individual enum values.  A full
    enum-type recreation would be required; left as a no-op (matches
    4226efc73854's downgrade).
    """
    pass
