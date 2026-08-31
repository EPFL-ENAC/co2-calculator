# codeql[py/unused-global-variable]
"""delete orphaned null created_by explore projects

Revision ID: 95fe938000d4
Revises: 6e32aa42f6f4
Create Date: 2026-08-28 16:40:46.507252

"""

from collections.abc import Sequence

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "95fe938000d4"  # noqa: F841
down_revision: str | Sequence[str] | None = "6e32aa42f6f4"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841

# Deletes, in FK order (children first — none of these FKs cascade on
# delete), every Simulator_Explore carbon_projects row (and its report
# tree) left with created_by IS NULL. #2293 (ff4f9bac0339) scoped
# Simulator_Explore projects to (unit_id, created_by), but the pre-#2293
# create_explore never stamped created_by, and Postgres unique indexes
# treat NULLs as distinct — so those rows were admitted without error and
# are now unreachable dead data (_get_explore_project always filters
# created_by == <int>, never NULL). #2458.
#
# data_entry_emissions is not listed: its FK to data_entries is
# ondelete=CASCADE, so it clears automatically when data_entries rows go.
_DELETE_DATA_ENTRIES = """
    DELETE FROM data_entries
    WHERE carbon_report_module_id IN (
        SELECT crm.id
        FROM carbon_report_modules crm
        JOIN carbon_reports cr ON cr.id = crm.carbon_report_id
        JOIN carbon_projects cp ON cp.id = cr.carbon_project_id
        WHERE cp.carbon_report_type = 'Simulator_Explore'
          AND cp.created_by IS NULL
    )
"""

_DELETE_CARBON_REPORT_MODULES = """
    DELETE FROM carbon_report_modules
    WHERE carbon_report_id IN (
        SELECT cr.id
        FROM carbon_reports cr
        JOIN carbon_projects cp ON cp.id = cr.carbon_project_id
        WHERE cp.carbon_report_type = 'Simulator_Explore'
          AND cp.created_by IS NULL
    )
"""

_DELETE_CARBON_REPORTS = """
    DELETE FROM carbon_reports
    WHERE carbon_project_id IN (
        SELECT id FROM carbon_projects
        WHERE carbon_report_type = 'Simulator_Explore' AND created_by IS NULL
    )
"""

_DELETE_CARBON_PROJECTS = """
    DELETE FROM carbon_projects
    WHERE carbon_report_type = 'Simulator_Explore' AND created_by IS NULL
"""


def upgrade() -> None:
    """Delete orphaned NULL-created_by Simulator_Explore projects and dependents.

    Leaf to root: data_entries -> carbon_report_modules -> carbon_reports
    -> carbon_projects. See module docstring for why these rows are
    unreachable dead data rather than legitimate ones.
    """
    op.execute(_DELETE_DATA_ENTRIES)
    op.execute(_DELETE_CARBON_REPORT_MODULES)
    op.execute(_DELETE_CARBON_REPORTS)
    op.execute(_DELETE_CARBON_PROJECTS)


def downgrade() -> None:
    """No-op: intentionally irreversible.

    This migration only deletes rows that were already unreachable
    (orphaned by #2293/ff4f9bac0339) and changes no schema — there is
    nothing structural to revert, and deleted rows cannot be
    un-deleted. This is the accepted, documented one-way data cleanup
    approved for #2458.
    """
