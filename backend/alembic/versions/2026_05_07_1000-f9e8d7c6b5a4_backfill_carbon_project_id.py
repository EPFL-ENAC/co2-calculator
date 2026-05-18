# codeql[py/unused-global-variable]
"""backfill carbon_project_id for pre-existing calculator reports

Revision ID: f9e8d7c6b5a4
Revises: 05d68c9a6054
Create Date: 2026-05-07 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]

revision: str = "f9e8d7c6b5a4"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "e7f1a2b3c4d5"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Create one Calculator CarbonProject per unit and link existing reports."""
    # Step 1 — insert one Calculator project per unit that already has
    # carbon_reports without a project.  ON CONFLICT DO NOTHING makes this
    # idempotent so re-running the migration is safe.
    op.execute(
        """
        INSERT INTO carbon_projects
            (unit_id, carbon_report_type, is_viewable_by_unit_members)
        SELECT DISTINCT
            cr.unit_id,
            'Calculator'::carbon_report_type_enum,
            false
        FROM carbon_reports cr
        WHERE cr.carbon_project_id IS NULL
        ON CONFLICT (unit_id, carbon_report_type) DO NOTHING
        """
    )

    # Step 2 — link NULL reports to their Calculator project.
    op.execute(
        """
        UPDATE carbon_reports cr
        SET carbon_project_id = cp.id
        FROM carbon_projects cp
        WHERE cp.unit_id = cr.unit_id
          AND cp.carbon_report_type = 'Calculator'::carbon_report_type_enum
          AND cr.carbon_project_id IS NULL
        """
    )


def downgrade() -> None:
    """Null out the carbon_project_id for reports that were backfilled."""
    op.execute(
        """
        UPDATE carbon_reports
        SET carbon_project_id = NULL
        WHERE carbon_project_id IN (
            SELECT id FROM carbon_projects
            WHERE carbon_report_type = 'Calculator'::carbon_report_type_enum
        )
        """
    )
