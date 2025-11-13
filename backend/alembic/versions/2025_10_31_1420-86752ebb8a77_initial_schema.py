"""initial schema

Revision ID: 86752ebb8a77
Revises:
Create Date: 2025-10-31 14:20:30.308981

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
    "upgrade",
    "downgrade",
]

# revision identifiers, used by Alembic.
revision: str = "86752ebb8a77"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = None  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column(
            "unit_id", sa.String(), nullable=True, comment="EPFL unit/department ID"
        ),
        sa.Column("sciper", sa.String(), nullable=True, comment="EPFL SCIPER number"),
        sa.Column(
            "roles", sa.JSON(), nullable=False, comment="User roles for the user"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_sciper"), "users", ["sciper"], unique=True)
    op.create_index(op.f("ix_users_unit_id"), "users", ["unit_id"], unique=False)

    # Create resources table
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "unit_id", sa.String(), nullable=False, comment="EPFL unit/department ID"
        ),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column(
            "visibility",
            sa.String(),
            nullable=False,
            comment="Visibility level: public, private, unit",
        ),
        sa.Column("data", sa.JSON(), nullable=True, comment="Resource-specific data"),
        sa.Column(
            "resource_metadata", sa.JSON(), nullable=True, comment="Additional metadata"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resources_id"), "resources", ["id"], unique=False)
    op.create_index(op.f("ix_resources_name"), "resources", ["name"], unique=False)
    op.create_index(
        op.f("ix_resources_owner_id"), "resources", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_resources_unit_id"), "resources", ["unit_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_resources_unit_id"), table_name="resources")
    op.drop_index(op.f("ix_resources_owner_id"), table_name="resources")
    op.drop_index(op.f("ix_resources_name"), table_name="resources")
    op.drop_index(op.f("ix_resources_id"), table_name="resources")
    op.drop_table("resources")

    op.drop_index(op.f("ix_users_unit_id"), table_name="users")
    op.drop_index(op.f("ix_users_sciper"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
