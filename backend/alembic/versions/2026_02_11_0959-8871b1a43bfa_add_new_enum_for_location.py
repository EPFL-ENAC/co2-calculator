# codeql[py/unused-global-variable]
"""add new enum for location

Revision ID: 8871b1a43bfa
Revises: 54da9e258bf6
Create Date: 2026-02-11 09:59:12.333301

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
revision: str = "8871b1a43bfa"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "54da9e258bf6"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    enum_type = sa.Enum("plane", "train", name="transportmodeenum")
    enum_type.create(op.get_bind(), checkfirst=True)

    op.alter_column(
        "locations",
        "transport_mode",
        existing_type=sa.VARCHAR(),
        type_=enum_type,
        existing_nullable=False,
        postgresql_using="transport_mode::transportmodeenum",
    )


def downgrade() -> None:
    """Downgrade schema."""
    enum_type = sa.Enum("plane", "train", name="transportmodeenum")

    op.alter_column(
        "locations",
        "transport_mode",
        existing_type=enum_type,
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )

    enum_type.drop(op.get_bind(), checkfirst=True)
