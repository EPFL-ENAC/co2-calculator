"""remove permissions field from user

Revision ID: cfe36a1dac9a
Revises: 9f3a4b5c6d7e
Create Date: 2026-01-06 14:05:45.872196

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cfe36a1dac9a"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "9f3a4b5c6d7e"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Remove permissions column from users table
    op.drop_column("users", "permissions")


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add permissions column if rolling back
    from sqlalchemy.dialects import postgresql

    op.add_column(
        "users",
        sa.Column(
            "permissions",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::json"),
        ),
    )
