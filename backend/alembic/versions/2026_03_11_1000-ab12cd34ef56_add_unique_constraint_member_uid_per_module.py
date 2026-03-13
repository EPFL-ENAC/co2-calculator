# codeql[py/unused-global-variable]
"""add unique constraint for member user_institutional_id per carbon_report_module

Revision ID: ab12cd34ef56
Revises: f1a2b3c4d5e6
Create Date: 2026-03-11 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]

# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    # Enforce one entry per member (user_institutional_id) per carbon_report_module.
    # Only applies to headcount member entries (data_entry_type_id = 1) that carry
    # a non-null institutional ID in their JSON data column.
    op.execute(
        """
        CREATE UNIQUE INDEX data_entries_unique_member_uid_per_module_idx
        ON data_entries (carbon_report_module_id, (data->>'user_institutional_id'))
        WHERE data_entry_type_id = 1
          AND data->>'user_institutional_id' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS data_entries_unique_member_uid_per_module_idx")
