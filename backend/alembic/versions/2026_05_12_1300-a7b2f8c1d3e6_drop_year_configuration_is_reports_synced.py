# codeql[py/unused-global-variable]
"""Drop year_configuration.is_reports_synced

Revision ID: a7b2f8c1d3e6
Revises: 8f29ed82872b
Create Date: 2026-05-12 13:00:00.000000

The column was declared but never written by any pipeline — only by the
PATCH endpoint, which no caller used.  The authoritative "carbon_reports
have been initialized for year N" signal lives in ``data_ingestion_jobs``
(the unit_sync job's terminal ``state=FINISHED && result=SUCCESS``).
Drop the redundant column.
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


revision: str = "a7b2f8c1d3e6"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "8f29ed82872b"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("year_configuration", "is_reports_synced")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "year_configuration",
        sa.Column(
            "is_reports_synced",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
