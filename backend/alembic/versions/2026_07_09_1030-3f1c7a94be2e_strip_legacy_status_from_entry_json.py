# codeql[py/unused-global-variable]
"""strip legacy status from entry json

Revision ID: 3f1c7a94be2e
Revises: 954eac6c95da
Create Date: 2026-07-09 10:30:00.000000

Data-only migration (issue #589, same shape as 954eac6c95da):

- The CSV ingest used to stamp ``payload["status"] = VALIDATED`` before
  handler validation. ``status`` is not in ``DATA_ENTRY_META_FIELDS``, so the
  payload mixin folded it into ``data_entries.data``, and the backoffice
  detailed export surfaced it as a bogus ``status`` column (always ``1``).
- The stamp never reached the ``data_entries.status`` column — the ingest's
  ``DataEntry(...)`` constructor does not pass it — so the key was pure
  pollution. The ingest no longer writes it; rows written before that must be
  cleaned in place, since the DB persists across deploys.
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
revision: str = "3f1c7a94be2e"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "954eac6c95da"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Strip the dead legacy ``status`` key from data_entries.data (JSON)."""
    op.execute(
        """
        UPDATE data_entries
        SET data = (data::jsonb - 'status')::json
        WHERE data::jsonb ? 'status'
        """
    )


def downgrade() -> None:
    """No-op: the key is dead weight the current code never reads or writes;
    the removed values carried no information (always VALIDATED)."""
