# codeql[py/unused-global-variable]
"""normalize entry data join keys

Revision ID: cf237968fba7
Revises: 09fe9e551783
Create Date: 2026-09-08 10:29:04.768632

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
revision: str = "cf237968fba7"  # noqa: F841
down_revision: str | Sequence[str] | None = "09fe9e551783"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841

# #2592: entries written before #1489 keep whatever format their payload had
# (currency "CHF", padded codes, "1.0" ids). Since #1489 the entry DTOs
# normalize those keys on write and the factor side was migrated
# (09fe9e551783), so an old entry can silently resolve no factor although the
# factor exists. This pass applies the DTO rules to data_entries.data for the
# join keys the shared types cover. Rows are only rewritten when a value
# changes; nothing is merged, deleted or added; re-running is a no-op.
#
# The rules and the key map are copies of app/schemas/fields.py and the
# *HandlerCreate DTOs. tests/unit/schemas/test_entry_data_migration.py pins
# both to the live DTOs so they cannot drift.

_ROW_SENTINEL = "RoW"
_INT_WITH_TRAILING_ZEROS = re.compile(r"^(\d+)\.0*$")

STRIP = "strip"
LOWER = "lower"
COUNTRY = "country"
IDENTIFIER = "identifier"
BLANK_TO_NONE = "blank_to_none"

_EQUIPMENT = {
    "equipment_id": STRIP,
    "name": STRIP,
    "equipment_class": STRIP,
    "sub_class": BLANK_TO_NONE,
}
_PURCHASE = {
    "name": STRIP,
    "purchase_institutional_code": STRIP,
    "purchase_additional_code": BLANK_TO_NONE,
    "currency": LOWER,
}
_RESEARCH_FACILITY = {
    "researchfacility_id": IDENTIFIER,
    "researchfacility_name": IDENTIFIER,
    "use_unit": STRIP,
}

# data_entry_type_id -> {key: rule}
RULES_BY_DATA_ENTRY_TYPE: dict[int, dict[str, str]] = {
    10: _EQUIPMENT,
    11: _EQUIPMENT,
    12: _EQUIPMENT,
    20: {"origin_iata": STRIP, "destination_iata": STRIP, "cabin_class": LOWER},
    21: {
        "origin_name": STRIP,
        "destination_name": STRIP,
        "origin_country_code": COUNTRY,
        "destination_country_code": COUNTRY,
        "cabin_class": LOWER,
    },
    30: {"building_name": STRIP, "room_name": STRIP},
    31: {"name": STRIP, "unit": STRIP},
    32: {"room_name": STRIP},
    40: {"service_type": STRIP, "provider": STRIP, "currency": LOWER},
    41: {"provider": STRIP, "usage_type": STRIP},
    50: {"category": STRIP, "subcategory": BLANK_TO_NONE},
    60: _PURCHASE,
    61: _PURCHASE,
    62: _PURCHASE,
    63: _PURCHASE,
    64: _PURCHASE,
    65: _PURCHASE,
    66: _PURCHASE,
    67: {"name": STRIP, "unit": STRIP},
    70: _RESEARCH_FACILITY,
    71: {**_RESEARCH_FACILITY, "researchfacility_type": STRIP},
}


def _normalize_identifier(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, str):
        stripped = value.strip()
        match = _INT_WITH_TRAILING_ZEROS.match(stripped)
        return match.group(1) if match else stripped
    return value


def normalize_value(rule: str, value: object) -> object:
    if rule == IDENTIFIER:
        return _normalize_identifier(value)
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if rule == LOWER:
        return normalized.lower()
    if rule == COUNTRY:
        if normalized.lower() == _ROW_SENTINEL.lower():
            return _ROW_SENTINEL
        return normalized.upper()
    if rule == BLANK_TO_NONE and normalized == "":
        return None
    return normalized


def normalize_entry_data(data_entry_type_id: int, data: dict) -> dict:
    """Apply the DTO rules to the keys present in ``data``; never adds keys."""
    rules = RULES_BY_DATA_ENTRY_TYPE.get(data_entry_type_id, {})
    return {
        key: normalize_value(rules[key], value) if key in rules else value
        for key, value in data.items()
    }


_CHUNK_SIZE = 5000


def _fetch_chunk(bind: sa.engine.Connection, after_id: int) -> list:
    return bind.execute(
        sa.text(
            "SELECT id, data_entry_type_id, data FROM data_entries"
            " WHERE data_entry_type_id IN :det_ids AND id > :after_id"
            " ORDER BY id LIMIT :limit"
        ).bindparams(sa.bindparam("det_ids", expanding=True)),
        {
            "det_ids": sorted(RULES_BY_DATA_ENTRY_TYPE),
            "after_id": after_id,
            "limit": _CHUNK_SIZE,
        },
    ).fetchall()


def _rewrite_row(bind: sa.engine.Connection, row: sa.Row) -> None:
    data = row.data
    if isinstance(data, str):
        data = json.loads(data)
    if not data:
        return
    normalized = normalize_entry_data(row.data_entry_type_id, data)
    if normalized == data:
        return
    bind.execute(
        sa.text("UPDATE data_entries SET data = CAST(:data AS jsonb) WHERE id = :id"),
        {"data": json.dumps(normalized), "id": row.id},
    )


def upgrade() -> None:
    """Rewrite data_entries.data join keys into the DTO-normalized form."""
    bind = op.get_bind()
    # Keyset pagination: data_entries holds a full year of purchases per
    # unit (150k+ rows per upload), so one fetchall would size the
    # migration Job's memory by the table.
    after_id = 0
    while True:
        rows = _fetch_chunk(bind, after_id)
        if not rows:
            return
        for row in rows:
            _rewrite_row(bind, row)
        after_id = rows[-1].id


def downgrade() -> None:
    """No-op: the pre-normalization formats are noise, not information."""
