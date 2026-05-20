# codeql[py/unused-global-variable]
"""year_configuration.configuration_completed (#1234-followup)

Tracks when the per-year ``unit_sync`` pipeline finished SUCCESS so
dispatch can refuse uploads for years that aren't yet provisioned (or
were never provisioned).  NULL on every existing row — set by the
handler on the next successful unit_sync run.  No backfill (v0.x).

Revision ID: a3b8c9d0e1f2
Revises: b1f7a2c9d4e0
Create Date: 2026-05-20 09:00:00.000000

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


revision: str = "a3b8c9d0e1f2"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "b1f7a2c9d4e0"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    op.add_column(
        "year_configuration",
        sa.Column(
            "configuration_completed",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("year_configuration", "configuration_completed")
