# codeql[py/unused-global-variable]
"""merge heads: backfill_carbon_project_id + emission_recalc_dedup_index

Revision ID: 1e56d303cc85
Revises: f9e8d7c6b5a4, f8a9b1c2d3e4
Create Date: 2026-05-07 16:45:28.360146

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]



# revision identifiers, used by Alembic.
revision: str = '1e56d303cc85' # noqa: F841
down_revision: Union[str, Sequence[str], None] = ('f9e8d7c6b5a4', 'f8a9b1c2d3e4') # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None # noqa: F841
depends_on: Union[str, Sequence[str], None] = None # noqa: F841


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
