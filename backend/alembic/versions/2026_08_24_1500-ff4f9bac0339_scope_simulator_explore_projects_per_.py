# codeql[py/unused-global-variable]
"""scope simulator explore projects per user

Revision ID: ff4f9bac0339
Revises: 277bf6757926
Create Date: 2026-08-24 15:00:06.164521

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
revision: str = "ff4f9bac0339"  # noqa: F841
down_revision: str | Sequence[str] | None = "277bf6757926"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(
        op.f("uq_carbon_projects_unit_type_nonplan"),
        table_name="carbon_projects",
        postgresql_where="(carbon_report_type <> 'Simulator_Plan'::carbon_report_type_enum)",
    )
    op.create_index(
        "uq_carbon_projects_unit_explore_creator",
        "carbon_projects",
        ["unit_id", "created_by"],
        unique=True,
        postgresql_where=sa.text("carbon_report_type = 'Simulator_Explore'"),
    )
    op.create_index(
        "uq_carbon_projects_unit_type_calculator",
        "carbon_projects",
        ["unit_id", "carbon_report_type"],
        unique=True,
        postgresql_where=sa.text("carbon_report_type = 'Calculator'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_carbon_projects_unit_type_calculator",
        table_name="carbon_projects",
        postgresql_where=sa.text("carbon_report_type = 'Calculator'"),
    )
    op.drop_index(
        "uq_carbon_projects_unit_explore_creator",
        table_name="carbon_projects",
        postgresql_where=sa.text("carbon_report_type = 'Simulator_Explore'"),
    )
    op.create_index(
        op.f("uq_carbon_projects_unit_type_nonplan"),
        "carbon_projects",
        ["unit_id", "carbon_report_type"],
        unique=True,
        postgresql_where="(carbon_report_type <> 'Simulator_Plan'::carbon_report_type_enum)",
    )
