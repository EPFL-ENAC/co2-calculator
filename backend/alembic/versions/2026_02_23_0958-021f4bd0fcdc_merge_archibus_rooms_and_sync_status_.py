# codeql[py/unused-global-variable]
"""merge archibus_rooms and sync_status heads

Revision ID: 021f4bd0fcdc
Revises: d24e845955cc, b1e2f3a4d5c6
Create Date: 2026-02-23 09:58:12.166731

"""

from typing import Sequence, Union

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "021f4bd0fcdc"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = ("d24e845955cc", "b1e2f3a4d5c6")  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
