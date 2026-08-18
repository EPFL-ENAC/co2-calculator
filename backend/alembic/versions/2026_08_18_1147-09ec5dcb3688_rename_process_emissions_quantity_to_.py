# codeql[py/unused-global-variable]
"""rename process emissions quantity to quantity_kg

Revision ID: 09ec5dcb3688
Revises: 98a2d551f336
Create Date: 2026-08-18 11:47:53.202988

Data-only migration (issue #2025, plan
``docs/src/implementation-plans/2025-processemissions-quantity-kg-rename.md``):

- The data manager renamed the process-emissions quantity column to
  ``quantity_kg`` in the data-description doc and the input data files, so
  the DTO field — and therefore the ``data_entries.data`` JSON key — follows.
- The DB persists across deploys, so entries written under the old key must
  be rewritten here; the emission formula reads ``quantity_kg`` from that
  JSON and would otherwise silently compute nothing for existing rows.
- Scoped to ``data_entry_type_id = 50`` (process_emissions): purchase and
  energy-combustion entries keep their own unrelated ``quantity`` key.
- Values are unchanged, so no recalculation is needed afterwards.
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
revision: str = "09ec5dcb3688"  # noqa: F841
down_revision: str | Sequence[str] | None = "98a2d551f336"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


# ``DataEntryTypeEnum.process_emissions``.  Inlined rather than imported:
# a migration must keep meaning even when the enum later changes.
_DET_PROCESS_EMISSIONS = 50

# Module-level so the round-trip test executes the exact shipped SQL
# (tests/integration/services/data_ingestion/test_quantity_kg_migration_pg.py)
# instead of a copy that can drift.
UPGRADE_SQL = f"""
    UPDATE data_entries
    SET data = (
        (data::jsonb - 'quantity')
        || jsonb_build_object('quantity_kg', data::jsonb -> 'quantity')
    )::json
    WHERE data_entry_type_id = {_DET_PROCESS_EMISSIONS}
      AND data::jsonb ? 'quantity'
"""

DOWNGRADE_SQL = f"""
    UPDATE data_entries
    SET data = (
        (data::jsonb - 'quantity_kg')
        || jsonb_build_object('quantity', data::jsonb -> 'quantity_kg')
    )::json
    WHERE data_entry_type_id = {_DET_PROCESS_EMISSIONS}
      AND data::jsonb ? 'quantity_kg'
"""


def upgrade() -> None:
    """Rename the ``quantity`` entry-JSON key to ``quantity_kg`` (#2025)."""
    op.execute(sa.text(UPGRADE_SQL))


def downgrade() -> None:
    """Restore ``quantity`` — the exact inverse; the previous revision's
    handler reads that key and nothing else writes ``quantity_kg``.
    """
    op.execute(sa.text(DOWNGRADE_SQL))
