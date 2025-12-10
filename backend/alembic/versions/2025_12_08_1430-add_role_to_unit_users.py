"""add_role_to_unit_users_and_principal_function_to_units

Revision ID: a1b2c3d4e5f6
Revises: 7372d6d5f1a4
Create Date: 2025-12-08 14:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "7372d6d5f1a4"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Add role column to unit_users table
    op.add_column(
        "unit_users",
        sa.Column(
            "role",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="co2.user.std",
        ),
    )
    op.create_index(op.f("ix_unit_users_role"), "unit_users", ["role"], unique=False)

    # Add principal_user_function to units table
    op.add_column(
        "units",
        sa.Column(
            "principal_user_function", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove principal_user_function from units
    op.drop_column("units", "principal_user_function")

    # Remove role from unit_users
    op.drop_index(op.f("ix_unit_users_role"), table_name="unit_users")
    op.drop_column("unit_users", "role")
