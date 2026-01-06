"""add permissions field to user

Revision ID: 9f3a4b5c6d7e
Revises: 8825f08d1f7f
Create Date: 2026-01-06 11:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f3a4b5c6d7e"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "8825f08d1f7f"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Add permissions JSON column to users table
    op.add_column(
        "users",
        sa.Column(
            "permissions",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::json"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove permissions column from users table
    op.drop_column("users", "permissions")
