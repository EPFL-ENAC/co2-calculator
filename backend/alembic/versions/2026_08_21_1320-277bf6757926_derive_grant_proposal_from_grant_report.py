# codeql[py/unused-global-variable]
"""derive grant proposal from grant report

Revision ID: 277bf6757926
Revises: ad1593afc72f
Create Date: 2026-08-21 13:20:14.923161

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
revision: str = "277bf6757926"  # noqa: F841
down_revision: str | Sequence[str] | None = "ad1593afc72f"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    stale = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id FROM carbon_projects p WHERE p.is_grant_proposal"
                " AND NOT EXISTS (SELECT 1 FROM carbon_reports r"
                " WHERE r.carbon_project_id = p.id AND r.is_grant)"
            )
        )
        .scalars()
        .all()
    )
    if stale:
        raise RuntimeError(
            f"carbon_projects {stale} are flagged is_grant_proposal without a grant report"
        )
    op.drop_column("carbon_projects", "is_grant_proposal")
    op.create_index(
        "uq_carbon_reports_project_grant",
        "carbon_reports",
        ["carbon_project_id"],
        unique=True,
        postgresql_where=sa.text("is_grant"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_carbon_reports_project_grant",
        table_name="carbon_reports",
        postgresql_where=sa.text("is_grant"),
    )
    op.add_column(
        "carbon_projects",
        sa.Column(
            "is_grant_proposal",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE carbon_projects p SET is_grant_proposal = true"
        " WHERE EXISTS (SELECT 1 FROM carbon_reports r"
        " WHERE r.carbon_project_id = p.id AND r.is_grant)"
    )
