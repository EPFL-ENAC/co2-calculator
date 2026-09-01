# codeql[py/unused-global-variable]
"""seed enum label translations

Revision ID: 7bff78de3264
Revises: fd12a7a0946f
Create Date: 2026-09-01 16:29:51.462666

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
revision: str = "7bff78de3264"  # noqa: F841
down_revision: str | Sequence[str] | None = "fd12a7a0946f"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


# Hand content (data migration, maintainer decision 2026-09-01, same pattern
# as the sius seed 3b5609f893f4): these classification values are enum-like
# keys in any locale, so both languages are seeded, the English display label
# included (#2613). Wording lifted verbatim from the frontend i18n files this
# seed replaces. A later factor-CSV upload upserts over the fr rows — the
# operator's wording wins.
_ENUM_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    # energy_combustion fuels (building_energycombustions_factors.csv)
    "name": {
        "natural_gas": ("Natural gas", "Gaz naturel"),
        "heating_oil": ("Heating oil", "Mazout"),
        "biomethane": ("Biomethane", "Biométhane"),
        "propane": ("Propane", "Propane"),
        "pellets": ("Pellets", "Granulés de bois"),
        "forest_chips": ("Forest chips", "Plaquettes forestières"),
        "wood_logs": ("Wood logs", "Bois bûche"),
    },
    # buildings room types (#173 lookup keys, building_rooms_factors.csv)
    "room_type": {
        "office": ("Office", "Bureau"),
        "miscellaneous": ("Miscellaneous", "Divers"),
        "laboratories": ("Laboratories", "Laboratoires"),
        "archives": ("Archives", "Archives"),
        "libraries": ("Libraries", "Bibliothèques"),
        "auditoriums": ("Auditoriums", "Auditoires"),
    },
    # animal facility housing types (researchfacilities_animals_factors.csv)
    "researchfacility_type": {
        "fish": ("Fish", "Poissons"),
        "rodent": ("Rodents", "Rongeurs"),
    },
    # external cloud service types (external_clouds_factors.csv;
    # virtualisation has no factor in the current catalog but may sit on
    # legacy entries)
    "service_type": {
        "storage": ("Storage", "Stockage"),
        "compute": ("Compute", "Calcul"),
        "virtualisation": ("Virtualisation", "Virtualisation"),
    },
}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    stmt = sa.text(
        "INSERT INTO classification_translations"
        " (field_name, value, lang, label)"
        " VALUES (:field, :value, :lang, :label)"
        " ON CONFLICT (field_name, value, lang)"
        " DO UPDATE SET label = EXCLUDED.label"
    )
    for field, labels in _ENUM_LABELS.items():
        for value, (en, fr) in labels.items():
            conn.execute(
                stmt, {"field": field, "value": value, "lang": "en", "label": en}
            )
            conn.execute(
                stmt, {"field": field, "value": value, "lang": "fr", "label": fr}
            )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    stmt = sa.text(
        "DELETE FROM classification_translations"
        " WHERE field_name = :field AND value = :value"
    )
    for field, labels in _ENUM_LABELS.items():
        for value in labels:
            conn.execute(stmt, {"field": field, "value": value})
