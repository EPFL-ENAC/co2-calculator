# codeql[py/unused-global-variable]
"""add kgco2 override to data entry

Revision ID: 0cb07d36bdf0
Revises: a7b2f8c1d3e6
Create Date: 2026-05-13 10:08:00.951062

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "0cb07d36bdf0"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "a7b2f8c1d3e6"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "data_entries", sa.Column("kg_co2eq_override", sa.Float(), nullable=True)
    )
    op.create_index(
        "ix_data_entries_kg_co2eq_override_notnull",
        "data_entries",
        ["kg_co2eq_override"],
        postgresql_where="kg_co2eq_override IS NOT NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_data_entries_kg_co2eq_override_notnull", table_name="data_entries"
    )
    op.drop_column("data_entries", "kg_co2eq_override")
