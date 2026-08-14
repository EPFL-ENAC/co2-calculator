# codeql[py/unused-global-variable]
"""migrate legacy traveler sentinels to -1 and null

Revision ID: 98a2d551f336
Revises: 9539986fa17b
Create Date: 2026-08-14 15:45:57.402648

Data-only migration (issue #1153):

- Professional Travel's ``user_institutional_id`` used to encode "Internal
  other" and "External other" as the ad-hoc strings ``__other_internal__``
  and ``__other_external__``. These are replaced by ``"-1"`` (Internal
  other) and JSON ``null`` (External other) respectively.
- The DB persists across deploys, so rows written under the old scheme must
  be backfilled here rather than assumed "moot after reseed".
- Only the two legacy sentinel values are touched; any other stored value
  (including unresolved source SCIPERs) is left untouched.
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
revision: str = "98a2d551f336"  # noqa: F841
down_revision: str | Sequence[str] | None = "9539986fa17b"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Rewrite legacy string traveler sentinels to -1 / null (#1153)."""
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"-1"')::json
            WHERE data->>'user_institutional_id' = '__other_internal__'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', 'null')::json
            WHERE data->>'user_institutional_id' = '__other_external__'
            """
        )
    )


def downgrade() -> None:
    """Restore the legacy string sentinels — the exact inverse; ``-1``/
    ``null`` are unknown to the resolver at the previous revision.
    """
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"__other_internal__"')::json
            WHERE data->>'user_institutional_id' = '-1'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(data::jsonb, '{user_institutional_id}', '"__other_external__"')::json
            WHERE data->>'user_institutional_id' IS NULL
              AND data::jsonb ? 'user_institutional_id'
            """
        )
    )
