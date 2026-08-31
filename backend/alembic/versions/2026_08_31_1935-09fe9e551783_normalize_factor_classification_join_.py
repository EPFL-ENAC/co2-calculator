# codeql[py/unused-global-variable]
"""normalize factor classification join keys

Revision ID: 09fe9e551783
Revises: 95fe938000d4
Create Date: 2026-08-31 19:35:18.518772

"""

import json
import re
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
revision: str = "09fe9e551783"  # noqa: F841
down_revision: str | Sequence[str] | None = "95fe938000d4"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841

# #1489: the shared field types in app/schemas/fields.py now normalize every
# factor-resolution join key symmetrically on both DTO families (strip; lower
# for currency/cabin_class/energy_type; upper for country codes with the RoW
# sentinel kept; trailing ".0" trimmed off numeric ids; blank to None).
# Existing factor rows written before that change may hold non-canonical
# values, which after the change would never match a normalized entry again
# (silent RoW fallbacks, missing computations) and would collide with the
# next CSV re-import as duplicate rows. This migration rewrites
# factors.classification to the same canonical form and merges rows whose
# identity (data_entry_type_id, year, emission_type_id, classification)
# collides after normalization: the lowest id survives, data_entry_emissions
# rows are repointed first (primary_factor_id references factors.id with
# ON DELETE CASCADE, so deleting without repointing would silently drop
# emission rows), then the duplicates are deleted.
#
# Entry data (data_entries.data) is deliberately NOT touched here: migrating
# validated emission data needs its own audited pass (see plan 1489).

_ROW_SENTINEL = "RoW"
_INT_WITH_TRAILING_ZEROS = re.compile(r"^(\d+)\.0*$")

# Keys mirrored from the DTO normalization in app/schemas/fields.py and the
# module DTOs. Keys not listed get the generic treatment: strip, blank to None.
_LOWER_KEYS = {"currency", "cabin_class", "energy_type"}
_COUNTRY_KEYS = {"country_code"}
_IDENTIFIER_KEYS = {"researchfacility_id", "researchfacility_name"}


def _normalize_value(key: str, value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if key in _LOWER_KEYS:
        normalized = normalized.lower()
    elif key in _COUNTRY_KEYS:
        if normalized.lower() == _ROW_SENTINEL.lower():
            normalized = _ROW_SENTINEL
        else:
            normalized = normalized.upper()
    elif key in _IDENTIFIER_KEYS:
        match = _INT_WITH_TRAILING_ZEROS.match(normalized)
        if match:
            normalized = match.group(1)
    if normalized == "":
        return None
    return normalized


def normalize_classification(classification: dict) -> dict:
    return {key: _normalize_value(key, value) for key, value in classification.items()}


def _identity(det: object, year: object, emission_type: object, cls: dict) -> str:
    return json.dumps(
        [det, year, emission_type, cls], sort_keys=True, separators=(",", ":")
    )


def upgrade() -> None:
    """Normalize factor classification values and merge resulting duplicates."""
    bind = op.get_bind()

    rows = bind.execute(
        sa.text(
            "SELECT id, data_entry_type_id, year, emission_type_id, classification"
            " FROM factors"
        )
    ).fetchall()

    groups: dict[str, list[int]] = {}
    normalized_by_id: dict[int, tuple[dict, bool]] = {}
    for row in rows:
        classification = row.classification
        if isinstance(classification, str):
            classification = json.loads(classification)
        if classification is None:
            classification = {}
        normalized = normalize_classification(classification)
        normalized_by_id[row.id] = (normalized, normalized != classification)
        key = _identity(
            row.data_entry_type_id, row.year, row.emission_type_id, normalized
        )
        groups.setdefault(key, []).append(row.id)

    # Merge collisions first: repoint emissions, then delete the duplicates.
    deleted: set[int] = set()
    for ids in groups.values():
        if len(ids) < 2:
            continue
        ids.sort()
        keeper, losers = ids[0], ids[1:]
        bind.execute(
            sa.text(
                "UPDATE data_entry_emissions SET primary_factor_id = :keeper"
                " WHERE primary_factor_id IN :losers"
            ).bindparams(sa.bindparam("losers", expanding=True)),
            {"keeper": keeper, "losers": losers},
        )
        bind.execute(
            sa.text("DELETE FROM factors WHERE id IN :losers").bindparams(
                sa.bindparam("losers", expanding=True)
            ),
            {"losers": losers},
        )
        deleted.update(losers)

    # Then rewrite the surviving rows that changed. No transient identity
    # collision is possible: survivors have pairwise-distinct normalized
    # identities, and any old value equal to a survivor's new value would
    # have normalized into the same group and been merged above.
    for factor_id, (normalized, changed) in normalized_by_id.items():
        if not changed or factor_id in deleted:
            continue
        bind.execute(
            sa.text(
                "UPDATE factors SET classification = CAST(:cls AS jsonb) WHERE id = :id"
            ),
            {"cls": json.dumps(normalized), "id": factor_id},
        )


def downgrade() -> None:
    """No-op: the pre-normalization casing and merged duplicates are gone."""
