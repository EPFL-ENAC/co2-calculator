# codeql[py/unused-global-variable]
"""strip legacy primary_factor_id and null purchase codes from entry json

Revision ID: 954eac6c95da
Revises: d88cd2f143bf
Create Date: 2026-07-06 11:24:26.373936

Data-only migration (plan 1661, v1.0 follow-up — the DB persists across
deploys now, so rows written before the primary_factor_id removal must be
cleaned in place instead of waiting for a reseed that no longer happens):

- ``data_entries.data.primary_factor_id`` is a dead denormalization: no
  code reads it since the 1661 refactor (factors are resolved on demand),
  but report exports would expose the stale key.
- A purchase entry persisted with an explicit-null
  ``purchase_institutional_code`` would be rejected by the new update
  validator on EVERY PATCH (present-but-null is invalid; key-absent means
  "not updating"), making the row permanently un-editable. Stripping the
  null key restores the key-absent shape the CSV ingest always wrote.
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
revision: str = "954eac6c95da"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "d88cd2f143bf"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Strip dead/poisonous legacy keys from data_entries.data (JSON column)."""
    op.execute(
        """
        UPDATE data_entries
        SET data = (data::jsonb - 'primary_factor_id')::json
        WHERE data::jsonb ? 'primary_factor_id'
        """
    )
    op.execute(
        """
        UPDATE data_entries
        SET data = (data::jsonb - 'purchase_institutional_code')::json
        WHERE data::jsonb ? 'purchase_institutional_code'
          AND data::jsonb ->> 'purchase_institutional_code' IS NULL
        """
    )


def downgrade() -> None:
    """No-op: both keys are dead weight the current code never reads or
    writes; the removed values are not recoverable and not needed."""
