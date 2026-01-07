"""create travel impact factors tables

Revision ID: 0263c0bf7cfe
Revises: 26ea90b9cd39
Create Date: 2026-01-16 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0263c0bf7cfe"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "26ea90b9cd39"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Check if tables already exist (they might have been created manually)
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create plane_impact_factors table if it doesn't exist
    table_created = "plane_impact_factors" not in existing_tables
    if table_created:
        op.create_table(
            "plane_impact_factors",
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
            sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "factor_type",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column(
                "category",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column("impact_score", sa.Float(), nullable=False),
            sa.Column("rfi_adjustment", sa.Float(), nullable=False),
            sa.Column("min_distance", sa.Float(), nullable=True),
            sa.Column("max_distance", sa.Float(), nullable=True),
            sa.Column(
                "valid_from",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "valid_to",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create indexes for plane_impact_factors if they don't exist
    # If table was just created, indexes definitely don't exist
    # If table already existed, check existing indexes
    if table_created:
        # Table was just created, so indexes don't exist - create them
        op.create_index(
            op.f("ix_plane_impact_factors_created_by"),
            "plane_impact_factors",
            ["created_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_plane_impact_factors_factor_type"),
            "plane_impact_factors",
            ["factor_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_plane_impact_factors_category"),
            "plane_impact_factors",
            ["category"],
            unique=False,
        )
        op.create_index(
            op.f("ix_plane_impact_factors_updated_by"),
            "plane_impact_factors",
            ["updated_by"],
            unique=False,
        )
    else:
        # Table already exists, check if indexes exist before creating
        # Also check if columns exist before creating indexes
        existing_indexes = [
            idx["name"] for idx in inspector.get_indexes("plane_impact_factors")
        ]
        existing_columns = [
            col["name"] for col in inspector.get_columns("plane_impact_factors")
        ]

        if (
            "created_by" in existing_columns
            and "ix_plane_impact_factors_created_by" not in existing_indexes
        ):
            op.create_index(
                op.f("ix_plane_impact_factors_created_by"),
                "plane_impact_factors",
                ["created_by"],
                unique=False,
            )
        if (
            "factor_type" in existing_columns
            and "ix_plane_impact_factors_factor_type" not in existing_indexes
        ):
            op.create_index(
                op.f("ix_plane_impact_factors_factor_type"),
                "plane_impact_factors",
                ["factor_type"],
                unique=False,
            )
        if (
            "category" in existing_columns
            and "ix_plane_impact_factors_category" not in existing_indexes
        ):
            op.create_index(
                op.f("ix_plane_impact_factors_category"),
                "plane_impact_factors",
                ["category"],
                unique=False,
            )
        if (
            "updated_by" in existing_columns
            and "ix_plane_impact_factors_updated_by" not in existing_indexes
        ):
            op.create_index(
                op.f("ix_plane_impact_factors_updated_by"),
                "plane_impact_factors",
                ["updated_by"],
                unique=False,
            )

    # Create train_impact_factors table if it doesn't exist
    train_table_created = "train_impact_factors" not in existing_tables
    if train_table_created:
        op.create_table(
            "train_impact_factors",
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
            sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "factor_type",
                sqlmodel.sql.sqltypes.AutoString(length=50),
                nullable=False,
            ),
            sa.Column(
                "countrycode",
                sqlmodel.sql.sqltypes.AutoString(length=10),
                nullable=False,
            ),
            sa.Column("impact_score", sa.Float(), nullable=False),
            sa.Column(
                "valid_from",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "valid_to",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        # Table exists, check if it has all required columns and add missing ones
        existing_train_columns = [
            col["name"] for col in inspector.get_columns("train_impact_factors")
        ]

        # Add countrycode column if it doesn't exist
        # Since this is a new table, it should be empty, so we can add it as NOT NULL
        # If there's existing data, we'll need to handle it separately
        if "countrycode" not in existing_train_columns:
            # Check if table has any rows - if empty, we can safely add NOT NULL column
            # For safety, we'll add it as nullable first, but this should be fixed
            # in a follow-up migration if the table has data
            op.add_column(
                "train_impact_factors",
                sa.Column(
                    "countrycode",
                    sqlmodel.sql.sqltypes.AutoString(length=10),
                    nullable=True,  # Start as nullable for safety
                ),
            )

    # Create indexes for train_impact_factors if they don't exist
    # If table was just created, indexes definitely don't exist
    # If table already existed, check existing indexes
    if train_table_created:
        # Table was just created, so indexes don't exist - create them
        op.create_index(
            op.f("ix_train_impact_factors_created_by"),
            "train_impact_factors",
            ["created_by"],
            unique=False,
        )
        op.create_index(
            op.f("ix_train_impact_factors_factor_type"),
            "train_impact_factors",
            ["factor_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_train_impact_factors_countrycode"),
            "train_impact_factors",
            ["countrycode"],
            unique=False,
        )
        op.create_index(
            op.f("ix_train_impact_factors_updated_by"),
            "train_impact_factors",
            ["updated_by"],
            unique=False,
        )
    else:
        # Table already exists, check if indexes exist before creating
        # Also check if columns exist before creating indexes
        existing_train_indexes = [
            idx["name"] for idx in inspector.get_indexes("train_impact_factors")
        ]
        existing_train_columns = [
            col["name"] for col in inspector.get_columns("train_impact_factors")
        ]

        if (
            "created_by" in existing_train_columns
            and "ix_train_impact_factors_created_by" not in existing_train_indexes
        ):
            op.create_index(
                op.f("ix_train_impact_factors_created_by"),
                "train_impact_factors",
                ["created_by"],
                unique=False,
            )
        if (
            "factor_type" in existing_train_columns
            and "ix_train_impact_factors_factor_type" not in existing_train_indexes
        ):
            op.create_index(
                op.f("ix_train_impact_factors_factor_type"),
                "train_impact_factors",
                ["factor_type"],
                unique=False,
            )
        if (
            "countrycode" in existing_train_columns
            and "ix_train_impact_factors_countrycode" not in existing_train_indexes
        ):
            op.create_index(
                op.f("ix_train_impact_factors_countrycode"),
                "train_impact_factors",
                ["countrycode"],
                unique=False,
            )
        if (
            "updated_by" in existing_train_columns
            and "ix_train_impact_factors_updated_by" not in existing_train_indexes
        ):
            op.create_index(
                op.f("ix_train_impact_factors_updated_by"),
                "train_impact_factors",
                ["updated_by"],
                unique=False,
            )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes for train_impact_factors
    op.drop_index(
        op.f("ix_train_impact_factors_updated_by"), table_name="train_impact_factors"
    )
    op.drop_index(
        op.f("ix_train_impact_factors_countrycode"), table_name="train_impact_factors"
    )
    op.drop_index(
        op.f("ix_train_impact_factors_factor_type"), table_name="train_impact_factors"
    )
    op.drop_index(
        op.f("ix_train_impact_factors_created_by"), table_name="train_impact_factors"
    )
    op.drop_table("train_impact_factors")

    # Drop indexes for plane_impact_factors
    op.drop_index(
        op.f("ix_plane_impact_factors_updated_by"), table_name="plane_impact_factors"
    )
    op.drop_index(
        op.f("ix_plane_impact_factors_category"), table_name="plane_impact_factors"
    )
    op.drop_index(
        op.f("ix_plane_impact_factors_factor_type"), table_name="plane_impact_factors"
    )
    op.drop_index(
        op.f("ix_plane_impact_factors_created_by"), table_name="plane_impact_factors"
    )
    op.drop_table("plane_impact_factors")
