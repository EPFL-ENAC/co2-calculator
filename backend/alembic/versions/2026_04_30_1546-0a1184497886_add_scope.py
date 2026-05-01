# codeql[py/unused-global-variable]
"""add scope

Revision ID: 0a1184497886
Revises: 451937f20b2d
Create Date: 2026-04-30 15:46:13.014972

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "0a1184497886"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "451937f20b2d"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "data_entry_emissions",
        sa.Column("scope", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("data_entry_emissions", "scope")
