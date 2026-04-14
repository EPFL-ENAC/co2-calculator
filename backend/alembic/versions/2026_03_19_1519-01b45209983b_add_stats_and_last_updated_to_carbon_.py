# codeql[py/unused-global-variable]
"""add_stats_and_last_updated_to_carbon_reports

Revision ID: 01b45209983b
Revises: 2026031801
Create Date: 2026-03-19 15:19:29.330566

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
revision: str = "01b45209983b"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "2026031801"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Add stats, last_updated, completion_progress, and overall_status columns
    to carbon_reports table."""
    op.add_column(
        "carbon_reports",
        sa.Column(
            "last_updated",
            sa.Integer(),
            nullable=True,
            comment=(
                "Timestamp of last update (epoch seconds)"
                " - used for concurrency control and freshness checks"
                " - updated automatically on data changes in any child module"
                " - can be null if never updated since creation"
            ),
        ),
    )
    op.add_column(
        "carbon_reports",
        sa.Column(
            "stats",
            sa.JSON(),
            nullable=True,
            comment=(
                "Optional JSON field to store pre-calculated statistics for the report"
                " - aggregates stats from all child CarbonReportModule records"
                " - includes scope totals, by_emission_type, computed_at, entry_count"
                " - helps optimize frontend perf by avoid on-the-fly calculations"
            ),
        ),
    )
    op.add_column(
        "carbon_reports",
        sa.Column(
            "completion_progress",
            sa.String(length=20),
            nullable=True,
            comment=(
                "String representation of completion progress (e.g., '5/7')"
                " - shows how many modules are completed vs total modules"
                " - updated automatically when child module status changes"
            ),
        ),
    )
    op.add_column(
        "carbon_reports",
        sa.Column(
            "overall_status",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment=(
                "Overall status inferred from child modules:"
                " 0=NOT_STARTED (no modules started),"
                " 1=IN_PROGRESS (some but not all modules completed),"
                " 2=VALIDATED (all modules validated)"
            ),
        ),
    )


def downgrade() -> None:
    """Remove stats, last_updated, completion_progress, and overall_status columns
    from carbon_reports table."""
    op.drop_column("carbon_reports", "overall_status")
    op.drop_column("carbon_reports", "completion_progress")
    op.drop_column("carbon_reports", "stats")
    op.drop_column("carbon_reports", "last_updated")
