# codeql[py/unused-global-variable]
"""seed energy type label translations

Revision ID: fd12a7a0946f
Revises: 3b5609f893f4
Create Date: 2026-09-01 10:42:30.700155

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
revision: str = "fd12a7a0946f"  # noqa: F841
down_revision: str | Sequence[str] | None = "3b5609f893f4"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


# Hand content (data migration, maintainer decision 2026-09-01, same
# pattern as the sius seed 3b5609f893f4): energy_type is a two-value
# reference vocabulary ("electric"/"thermal", enforced by
# BuildingRoomFactor's validator) whose stored value is an enum-like code
# in any locale — so both languages are seeded, the English display label
# included. Nothing renders it in the UI yet; the labels are ready for
# the embodied-energy "heating type" exposure follow-up.
_ENERGY_TYPE_LABELS: dict[str, tuple[str, str]] = {
    "electric": ("Electric", "Électrique"),
    "thermal": ("Thermal", "Thermique"),
}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    stmt = sa.text(
        "INSERT INTO classification_translations"
        " (field_name, value, lang, label)"
        " VALUES ('energy_type', :value, :lang, :label)"
        " ON CONFLICT (field_name, value, lang)"
        " DO UPDATE SET label = EXCLUDED.label"
    )
    for value, (en, fr) in _ENERGY_TYPE_LABELS.items():
        conn.execute(stmt, {"value": value, "lang": "en", "label": en})
        conn.execute(stmt, {"value": value, "lang": "fr", "label": fr})


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "DELETE FROM classification_translations WHERE field_name = 'energy_type'"
    )
