# codeql[py/unused-global-variable]
"""grant budget on reports and modules

Revision ID: 9539986fa17b
Revises: 3d74009feee4
Create Date: 2026-08-05 09:55:48.679830

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
revision: str = "9539986fa17b"  # noqa: F841
down_revision: str | Sequence[str] | None = "3d74009feee4"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "carbon_report_modules", sa.Column("budgets", sa.JSON(), nullable=True)
    )
    op.add_column("carbon_reports", sa.Column("budget", sa.Float(), nullable=True))
    op.add_column(
        "carbon_reports",
        sa.Column("budget_currency", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("carbon_reports", "budget_currency")
    op.drop_column("carbon_reports", "budget")
    op.drop_column("carbon_report_modules", "budgets")
