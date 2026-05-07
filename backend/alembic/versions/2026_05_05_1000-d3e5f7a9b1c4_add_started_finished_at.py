# codeql[py/unused-global-variable]
"""add started_at / finished_at to data_ingestion_jobs

Revision ID: d3e5f7a9b1c4
Revises: 3f8147b5e516
Create Date: 2026-05-05 10:00:00.000000

Plan 310-C observability columns.  Adds two nullable timestamps that, with
``locked_at`` (Plan 310-A), distinguish per-attempt timing from total
wall-clock duration:

- ``started_at`` is set ONCE on the first claim and stays put across
  retries.  Used to compute ``finished_at - started_at`` as true total
  duration regardless of how many attempts a job needed.
- ``finished_at`` is set when the job reaches ``state=FINISHED``.

``locked_at`` (already present) updates on every claim and is per-attempt;
it answers "is this lock stale?" not "how long did the job take?".

Both columns are nullable to avoid a backfill — pre-existing rows simply
lack timing data, which the dashboard query (see plan 310-c) treats as
"unknown" via ``WHERE finished_at IS NOT NULL`` filters.

Chains off the single dev head ``3f8147b5e516`` (search-locations).
Earlier drafts of this migration carried a multi-revision merge to
bridge two pre-existing heads, but ``dev`` linearised its chain
(``3f8147b5e516``'s parent is now ``c2d4e6f8a012``), so a single
parent is correct.
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


revision: str = "d3e5f7a9b1c4"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "05d68c9a6054"
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "data_ingestion_jobs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "data_ingestion_jobs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("data_ingestion_jobs", "finished_at")
    op.drop_column("data_ingestion_jobs", "started_at")
