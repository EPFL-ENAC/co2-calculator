"""add countrycode to locations table

Revision ID: 26ea90b9cd39
Revises: ce20d9691b22
Create Date: 2026-01-16 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26ea90b9cd39"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "ce20d9691b22"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    # Add countrycode column to locations table
    op.add_column(
        "locations",
        sa.Column(
            "countrycode",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=True,
        ),
    )
    # Create index on countrycode
    op.create_index(
        op.f("ix_locations_countrycode"),
        "locations",
        ["countrycode"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index
    op.drop_index(op.f("ix_locations_countrycode"), table_name="locations")
    # Drop column
    op.drop_column("locations", "countrycode")
