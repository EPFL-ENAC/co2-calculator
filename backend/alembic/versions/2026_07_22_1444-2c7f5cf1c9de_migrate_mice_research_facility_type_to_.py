# codeql[py/unused-global-variable]
"""migrate mice research facility type to rodent

Revision ID: 2c7f5cf1c9de
Revises: ca72e51fd409
Create Date: 2026-07-22 14:44:43.536722

Data-only migration (issue #866):

- The animal-facility type ``mice`` was renamed to ``rodent``. The resolver
  ``resolve_research_facilities`` now raises on any type outside
  ``{rodent, fish}``, so rows persisted before the rename would break the
  next emission recalculation.
- Both the factor classification and the entry payload carry the type as a
  free-text value, so they must be rewritten in place; emissions are keyed
  by enum id and need no change.
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


# revision identifiers, used by Alembic.
revision: str = "2c7f5cf1c9de"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "ca72e51fd409"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Rewrite the ``mice`` animal-facility type to ``rodent``."""
    op.execute(
        sa.text(
            """
            UPDATE factors
            SET classification = jsonb_set(
                classification, '{researchfacility_type}', '"rodent"'
            )
            WHERE classification->>'researchfacility_type' = 'mice'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(
                data::jsonb, '{researchfacility_type}', '"rodent"'
            )::json
            WHERE data->>'researchfacility_type' = 'mice'
            """
        )
    )


def downgrade() -> None:
    """Restore ``mice`` — the exact inverse; ``rodent`` is unknown to the
    resolver at the previous revision."""
    op.execute(
        sa.text(
            """
            UPDATE factors
            SET classification = jsonb_set(
                classification, '{researchfacility_type}', '"mice"'
            )
            WHERE classification->>'researchfacility_type' = 'rodent'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE data_entries
            SET data = jsonb_set(
                data::jsonb, '{researchfacility_type}', '"mice"'
            )::json
            WHERE data->>'researchfacility_type' = 'rodent'
            """
        )
    )
