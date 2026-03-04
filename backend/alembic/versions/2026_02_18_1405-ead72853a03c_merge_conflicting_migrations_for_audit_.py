# codeql[py/unused-global-variable]
"""merge conflicting migrations for audit tables

Revision ID: ead72853a03c
Revises: 36eb78f7b21f, 000000000000
Create Date: 2026-02-18 14:05:59.285132

"""

from typing import Sequence, Union

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "ead72853a03c"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = ("36eb78f7b21f", "000000000000")  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
