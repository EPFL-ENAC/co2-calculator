"""remove_password_add_hierarchical_roles

Revision ID: 2025_11_14_0000
Revises: 86752ebb8a77
Create Date: 2025-11-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2025_11_14_0000"  # noqa: F841
down_revision: Union[str, None] = "86752ebb8a77"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Remove password authentication and update to hierarchical roles.

    BREAKING CHANGE: This migration removes password-based authentication
    and changes the roles structure. All users will need to re-login via OAuth.
    """
    # Drop password-related columns
    op.drop_column("users", "hashed_password")

    # Drop deprecated columns
    op.drop_column("users", "full_name")
    op.drop_column("users", "unit_id")
    op.drop_column("users", "is_superuser")

    # Note: roles column type change is handled by SQLAlchemy
    # The JSON column will now store List[dict] instead of List[str]
    # Existing data is nulled out as users need to re-login
    op.execute("UPDATE users SET roles = '[]'::json")


def downgrade() -> None:
    """Restore password authentication and flat roles structure.

    WARNING: This downgrade cannot recover deleted data.
    """
    # Re-add removed columns
    op.add_column("users", sa.Column("hashed_password", sa.String(), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("unit_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), nullable=True))

    # Set defaults for re-added columns
    op.execute("UPDATE users SET hashed_password = '', is_superuser = false")
    op.alter_column("users", "hashed_password", nullable=False)

    # Create index on unit_id
    op.create_index("ix_users_unit_id", "users", ["unit_id"], unique=False)

    # Note: roles data structure cannot be automatically converted back
    # Users will need to have their roles manually restored
    op.execute("UPDATE users SET roles = '[]'::json")
