# codeql[py/unused-global-variable]
"""carbon_report_modules is_active

Adds the per-module Active flag: Simulator Plan modules can be excluded
from report sums/stats. Always true for Calculator/Explore modules.

Revision ID: ca72e51fd409
Revises: f9d210343448
Create Date: 2026-07-15 23:32:59.400023

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "ca72e51fd409"  # noqa: F841
down_revision: str | Sequence[str] | None = "f9d210343448"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "carbon_report_modules",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("carbon_report_modules", "is_active")
