# codeql[py/unused-global-variable]
"""Remove audit columns from locations table

Revision ID: update_locations_table
Revises: drop_headcounts_table
Create Date: 2026-02-05 15:00:00.000000

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
revision: str = "update_locations_table"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "drop_headcounts_table"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Remove audit columns from locations table."""
    # Drop indexes first
    op.drop_index(op.f("ix_locations_created_by"), table_name="locations")
    op.drop_index(op.f("ix_locations_updated_by"), table_name="locations")

    # Drop columns
    op.drop_column("locations", "created_at")
    op.drop_column("locations", "updated_at")
    op.drop_column("locations", "created_by")
    op.drop_column("locations", "updated_by")


def downgrade() -> None:
    """Add audit columns back to locations table."""
    # Add columns
    op.add_column(
        "locations",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "locations",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "locations",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "locations",
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )

    # Recreate indexes
    op.create_index(
        op.f("ix_locations_created_by"), "locations", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_locations_updated_by"), "locations", ["updated_by"], unique=False
    )
