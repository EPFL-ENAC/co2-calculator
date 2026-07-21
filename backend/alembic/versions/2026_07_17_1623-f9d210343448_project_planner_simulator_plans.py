# codeql[py/unused-global-variable]
"""project planner simulator plans

Adds creator tracking to carbon_projects and relaxes the one-project-per-
(unit, type) constraint so a unit can hold multiple Simulator_Plan projects
(each plan is one project row identified by its name).

Note: the downgrade cannot recreate uq_carbon_projects_unit_type if a unit
already has more than one Simulator_Plan project.

Revision ID: f9d210343448
Revises: 8eeff0a9fa26
Create Date: 2026-07-14 16:23:00.000000

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
revision: str = "f9d210343448"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "8eeff0a9fa26"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "carbon_projects",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "carbon_projects",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_carbon_projects_created_by_users",
        "carbon_projects",
        "users",
        ["created_by"],
        ["id"],
    )
    op.drop_constraint(
        "uq_carbon_projects_unit_type", "carbon_projects", type_="unique"
    )
    # One project per (unit, type) still holds for Calculator and
    # Simulator_Explore; Simulator_Plan allows many projects per unit.
    op.create_index(
        "uq_carbon_projects_unit_type_nonplan",
        "carbon_projects",
        ["unit_id", "carbon_report_type"],
        unique=True,
        postgresql_where=sa.text("carbon_report_type != 'Simulator_Plan'"),
    )
    # Plan names are URL identifiers: unique per unit among plan projects.
    op.create_index(
        "uq_carbon_projects_unit_plan_name",
        "carbon_projects",
        ["unit_id", "name"],
        unique=True,
        postgresql_where=sa.text("carbon_report_type = 'Simulator_Plan'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_carbon_projects_unit_plan_name", table_name="carbon_projects")
    op.drop_index("uq_carbon_projects_unit_type_nonplan", table_name="carbon_projects")
    op.create_unique_constraint(
        "uq_carbon_projects_unit_type",
        "carbon_projects",
        ["unit_id", "carbon_report_type"],
    )
    op.drop_constraint(
        "fk_carbon_projects_created_by_users", "carbon_projects", type_="foreignkey"
    )
    op.drop_column("carbon_projects", "created_at")
    op.drop_column("carbon_projects", "created_by")
