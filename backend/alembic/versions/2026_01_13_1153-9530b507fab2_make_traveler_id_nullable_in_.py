"""make traveler_id nullable in professional_travels

Revision ID: 9530b507fab2
Revises: 3ed22e605e2a
Create Date: 2026-01-13 11:53:57.341499

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9530b507fab2"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "3ed22e605e2a"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Make traveler_id column nullable in professional_travels table
    op.alter_column(
        "professional_travels",
        "traveler_id",
        existing_type=sa.String(length=50),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Make traveler_id column NOT NULL again
    op.alter_column(
        "professional_travels",
        "traveler_id",
        existing_type=sa.String(length=50),
        nullable=False,
    )
