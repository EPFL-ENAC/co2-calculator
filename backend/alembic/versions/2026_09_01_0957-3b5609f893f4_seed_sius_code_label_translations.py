# codeql[py/unused-global-variable]
"""seed sius code label translations

Revision ID: 3b5609f893f4
Revises: 956c36805397
Create Date: 2026-09-01 09:57:15.423459

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
revision: str = "3b5609f893f4"  # noqa: F841
down_revision: str | Sequence[str] | None = "956c36805397"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


# Hand content (data migration, maintainer decision 2026-09-01): sius
# labels are reference data — the headcount factor CSVs carry no sius
# columns, so the CSV `_fr` convention has nothing to attach to. Seeded
# for BOTH languages: the stored value is a code in any locale, so unlike
# self-labeling fields its English label is also a lookup
# (`translated_code_fields` on the member handler reads these). Labels
# mirror frontend/src/i18n/headcount_factor.ts verbatim.
_SIUS_LABELS: dict[str, tuple[str, str]] = {
    "51": (
        "Professors",
        "Enseignant·e·s habilité·e·s à diriger une unité organisationnelle",
    ),
    "52": ("Other teaching staff", "Autres enseignant·e·s"),
    "53": (
        "Scientific collaborators",
        "Collaborateur·trices scientifiques",
    ),
    "54": (
        "Scientific and doctoral assistants",
        "Assistant·e·s et/ou doctorant·e·s",
    ),
    "56": (
        "Managerial staff",
        "Personnel de direction de la haute école",
    ),
    "57": ("Administrative staff", "Personnel administratif"),
    "58": ("Support staff", "Personnel de soutien"),
    "59": ("Operational staff", "Personnel d'exploitation"),
    "-1": ("Other staff", "Autre personnel"),
}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    stmt = sa.text(
        "INSERT INTO classification_translations"
        " (field_name, value, lang, label)"
        " VALUES ('sius_code', :value, :lang, :label)"
        " ON CONFLICT (field_name, value, lang)"
        " DO UPDATE SET label = EXCLUDED.label"
    )
    for value, (en, fr) in _SIUS_LABELS.items():
        conn.execute(stmt, {"value": value, "lang": "en", "label": en})
        conn.execute(stmt, {"value": value, "lang": "fr", "label": fr})


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM classification_translations WHERE field_name = 'sius_code'")
