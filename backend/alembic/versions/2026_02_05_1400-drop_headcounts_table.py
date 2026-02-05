# codeql[py/unused-global-variable]
"""Drop headcounts table

Revision ID: drop_headcounts_table
Revises: 6c749d29f53b
Create Date: 2026-02-05 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "drop_headcounts_table"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "6c749d29f53b"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Drop headcounts table."""
    # Drop indexes first
    op.drop_index(op.f("ix_headcounts_updated_by"), table_name="headcounts")
    op.drop_index(op.f("ix_headcounts_unit_id"), table_name="headcounts")
    op.drop_index(op.f("ix_headcounts_submodule"), table_name="headcounts")
    op.drop_index(op.f("ix_headcounts_sciper"), table_name="headcounts")
    op.drop_index(op.f("ix_headcounts_created_by"), table_name="headcounts")
    # Drop the table
    op.drop_table("headcounts")


def downgrade() -> None:
    """Recreate headcounts table."""
    op.create_table(
        "headcounts",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sciper", sqlmodel.sql.sqltypes.AutoString(length=6), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "function", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("fte", sa.Float(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "submodule",
            sa.Enum("member", "student", name="headcount_submodule_enum"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_headcounts_created_by"), "headcounts", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_headcounts_sciper"), "headcounts", ["sciper"], unique=False
    )
    op.create_index(
        op.f("ix_headcounts_submodule"), "headcounts", ["submodule"], unique=False
    )
    op.create_index(
        op.f("ix_headcounts_unit_id"), "headcounts", ["unit_id"], unique=False
    )
    op.create_index(
        op.f("ix_headcounts_updated_by"), "headcounts", ["updated_by"], unique=False
    )
