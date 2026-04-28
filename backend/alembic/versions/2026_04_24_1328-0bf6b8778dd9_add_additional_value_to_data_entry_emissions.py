# codeql[py/unused-global-variable]
"""add additional_value to data_entry_emissions

Revision ID: 0bf6b8778dd9
Revises: 4226efc73854
Create Date: 2026-04-24 13:28:43.442879

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
revision: str = "0bf6b8778dd9"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "4226efc73854"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "data_entry_emissions",
        sa.Column(
            "additional_value",
            sa.Float(),
            nullable=True,
            comment=(
                "Polymorphic physical quantity tied to this emission row. "
                "Unit is inferred from emission_type_id "
                "(e.g. km for commuting and travel, kg for food and waste)."
            ),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("data_entry_emissions", "additional_value")
