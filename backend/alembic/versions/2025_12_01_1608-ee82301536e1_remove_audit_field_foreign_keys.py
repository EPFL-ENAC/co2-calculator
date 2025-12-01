"""remove audit field foreign keys

Revision ID: ee82301536e1
Revises: c4a8e8052ee3
Create Date: 2025-12-01 16:08:47.621725

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee82301536e1"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "c4a8e8052ee3"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Remove foreign key constraints from audit fields."""
    # Users table
    op.drop_constraint("users_created_by_fkey", "users", type_="foreignkey")
    op.drop_constraint("users_updated_by_fkey", "users", type_="foreignkey")

    # Units table
    op.drop_constraint("units_created_by_fkey", "units", type_="foreignkey")
    op.drop_constraint("units_updated_by_fkey", "units", type_="foreignkey")


def downgrade() -> None:
    """Restore foreign key constraints."""
    # Users table
    op.create_foreign_key(
        "users_created_by_fkey", "users", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "users_updated_by_fkey", "users", "users", ["updated_by"], ["id"]
    )

    # Units table
    op.create_foreign_key(
        "units_created_by_fkey", "units", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "units_updated_by_fkey", "units", "users", ["updated_by"], ["id"]
    )
