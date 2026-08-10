# codeql[py/unused-global-variable]
"""grant proposal flag and project grant report

Revision ID: 3d74009feee4
Revises: 2c7f5cf1c9de
Create Date: 2026-08-05 09:10:41.031375

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
revision: str = "3d74009feee4"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "2c7f5cf1c9de"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "carbon_projects",
        sa.Column(
            "is_grant_proposal", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "carbon_reports",
        sa.Column("is_grant", sa.Boolean(), server_default="false", nullable=False),
    )
    # Widened with is_grant: a plan's Project Grant report shares its year
    # with the start-year report.
    op.drop_constraint(
        op.f("uq_carbon_reports_project_year"), "carbon_reports", type_="unique"
    )
    op.create_unique_constraint(
        "uq_carbon_reports_project_year",
        "carbon_reports",
        ["carbon_project_id", "year", "is_grant"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_carbon_reports_project_year", "carbon_reports", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_carbon_reports_project_year"),
        "carbon_reports",
        ["carbon_project_id", "year"],
    )
    op.drop_column("carbon_reports", "is_grant")
    op.drop_column("carbon_projects", "is_grant_proposal")
