# codeql[py/unused-global-variable]
"""remove purchase description

Revision ID: 30c096280772
Revises: a7b2f8c1d3e6
Create Date: 2026-05-13 15:15:06.594682

"""

from typing import Sequence, Union

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "30c096280772"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "a7b2f8c1d3e6"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


_agg_where = (
    "(((job_type)::text = 'aggregation'::text) AND (state = ANY ("
    "ARRAY['NOT_STARTED'::ingestion_state_enum, "
    "'QUEUED'::ingestion_state_enum, 'RUNNING'::ingestion_state_enum])))"
)
_recalc_where = (
    "(((job_type)::text = 'emission_recalc'::text) AND (state = ANY ("
    "ARRAY['NOT_STARTED'::ingestion_state_enum, "
    "'QUEUED'::ingestion_state_enum, 'RUNNING'::ingestion_state_enum])) "
    "AND (module_type_id IS NOT NULL) AND (data_entry_type_id IS NOT NULL) "
    "AND (year IS NOT NULL))"
)


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
