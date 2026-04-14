# codeql[py/unused-global-variable]
"""Add year_configuration table

Revision ID: a1b2c3d4e5f7
Revises: 253e62d79609
Create Date: 2026-03-31 00:00:00.000000

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
revision: str = "a1b2c3d4e5f7"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "253e62d79609"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "year_configuration",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("is_started", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_reports_synced", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "config",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_index(
        op.f("ix_year_configuration_year"),
        "year_configuration",
        ["year"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_year_configuration_year"), table_name="year_configuration")
    op.drop_table("year_configuration")
