# codeql[py/unused-global-variable]
"""backfill data_entries year and unit_id from carbon reports

Revision ID: 8eeff0a9fa26
Revises: 7bfda0d45f14
Create Date: 2026-07-17 15:11:57.728216

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
revision: str = "8eeff0a9fa26"  # noqa: F841
down_revision: str | Sequence[str] | None = "7bfda0d45f14"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Backfill denormalized scope columns on API-synced data entries.

    API providers built DataEntry rows without ``year``/``unit_id``
    (stage incident 2026-07-17), so the per-year cross-source replace
    DELETE — which keys on ``data_entries.year`` — never matched them
    and re-uploads mass-collided on DUPLICATE_INSTITUTIONAL_ID. Derive
    both from the entry's carbon report. (False-positive drop_index on
    uq_active_datasource_per_module pruned — partial unique index lives
    outside SQLModel metadata.)
    """
    op.execute(
        sa.text(
            """
            UPDATE data_entries de
            SET year = cr.year,
                unit_id = cr.unit_id
            FROM carbon_report_modules crm
            JOIN carbon_reports cr ON cr.id = crm.carbon_report_id
            WHERE de.carbon_report_module_id = crm.id
              AND (de.year IS NULL OR de.unit_id IS NULL)
            """
        )
    )


def downgrade() -> None:
    """No-op: the backfill only fills NULLs with derivable values."""
