"""add min max distance to plane impact factors

Revision ID: f7g8h9i0j1k2
Revises: 0263c0bf7cfe
Create Date: 2026-01-16 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7g8h9i0j1k2"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "0263c0bf7cfe"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Add min_distance and max_distance columns to plane_impact_factors table
    op.add_column(
        "plane_impact_factors",
        sa.Column("min_distance", sa.Float(), nullable=True),
    )
    op.add_column(
        "plane_impact_factors",
        sa.Column("max_distance", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop columns
    op.drop_column("plane_impact_factors", "max_distance")
    op.drop_column("plane_impact_factors", "min_distance")
