"""Audit, and on request apply, the #1489 join-key normalization on old rows.

Since #1489 every factor-resolution join key is normalized on write (shared
field types in ``app/schemas/fields.py``). Rows written before that may still
carry the old casing or whitespace, and factor resolution compares by exact
string equality. This script says, per platform, whether any such row exists
and what it would become. It never writes unless ``--apply`` is given.

    uv run python -m scripts.normalize_join_keys            # dry run, prints a report
    uv run python -m scripts.normalize_join_keys --apply    # rewrites the reported rows

The rules are copies of the DTO aliases; ``tests/unit/schemas/
test_join_key_normalization_rules.py`` pins them to the live DTOs so they
cannot drift. Factor rows whose identity would collide after normalization
are reported and never merged here: that is a manual decision (#2592).
"""

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db import engine
from app.models.data_entry import DataEntryStatusEnum, DataEntryTypeEnum
from app.modules.professional_travel.emissions import (
    PLANE_CABIN_MAP,
    TRAIN_CLASS_MAP,
)
from app.schemas.fields import ROW_COUNTRY_CODE
from app.utils.currencies import SUPPORTED_CURRENCIES

_INT_WITH_TRAILING_ZEROS = re.compile(r"^(\d+)\.0*$")
_CHUNK = 5000

STRIP = "strip"
LOWER = "lower"
COUNTRY = "country"
IDENTIFIER = "identifier"
BLANK_TO_NONE = "blank_to_none"

# ---------------------------------------------------------------- rules ----

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

# data_entry_type_id -> {key in data_entries.data: rule}
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

# factors.classification keys with a non-default rule; every other key is
# stripped and blank becomes None (the CSV provider's own convention).
FACTOR_RULES: dict[str, str] = {
    "currency": LOWER,
    "cabin_class": LOWER,
    "energy_type": LOWER,
    "country_code": COUNTRY,
    "researchfacility_id": IDENTIFIER,
    "researchfacility_name": IDENTIFIER,
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
        if normalized.lower() == ROW_COUNTRY_CODE.lower():
            return ROW_COUNTRY_CODE
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


def normalize_classification(classification: dict) -> dict:
    return {
        key: normalize_value(FACTOR_RULES.get(key, BLANK_TO_NONE), value)
        for key, value in classification.items()
    }


# --------------------------------------------------------------- audit ----


@dataclass
class Report:
    factors_scanned: int = 0
    factor_changes: Counter = field(default_factory=Counter)
    factor_rewrites: dict[int, dict] = field(default_factory=dict)
    duplicate_groups: list[list[int]] = field(default_factory=list)
    entries_scanned: int = 0
    entry_changes: Counter = field(default_factory=Counter)
    entry_validated: Counter = field(default_factory=Counter)
    entry_rewrites: dict[int, dict] = field(default_factory=dict)
    rejected: list[dict] = field(default_factory=list)


def _as_dict(value: object) -> dict:
    if isinstance(value, str):
        return json.loads(value)
    return dict(value or {})  # type: ignore[arg-type]  # jsonb comes back as dict


async def audit_factors(conn: AsyncConnection, report: Report) -> None:
    rows = (
        await conn.execute(
            text(
                "SELECT id, data_entry_type_id, year, emission_type_id,"
                " classification FROM factors"
            )
        )
    ).fetchall()
    groups: dict[str, list[int]] = {}
    for row in rows:
        report.factors_scanned += 1
        classification = _as_dict(row.classification)
        normalized = normalize_classification(classification)
        identity = json.dumps(
            [row.data_entry_type_id, row.year, row.emission_type_id, normalized],
            sort_keys=True,
        )
        groups.setdefault(identity, []).append(row.id)
        if normalized == classification:
            continue
        report.factor_rewrites[row.id] = normalized
        for key in classification:
            if normalized.get(key) != classification.get(key):
                report.factor_changes[
                    (DataEntryTypeEnum(row.data_entry_type_id).name, key)
                ] += 1
    report.duplicate_groups = [sorted(ids) for ids in groups.values() if len(ids) > 1]


def _rejected_reason(det: DataEntryTypeEnum, key: str, value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if key == "currency" and value not in SUPPORTED_CURRENCIES:
        return "currency not supported"
    if key == "cabin_class":
        allowed = PLANE_CABIN_MAP if det is DataEntryTypeEnum.plane else TRAIN_CLASS_MAP
        if value not in allowed:
            return "unknown cabin class"
    if key.endswith("country_code") and value != ROW_COUNTRY_CODE:
        if len(value) != 2 or not value.isalpha():
            return "malformed country code"
    return None


async def _entry_chunk(conn: AsyncConnection, after_id: int) -> list:
    return (
        await conn.execute(
            text(
                "SELECT id, data_entry_type_id, status, data FROM data_entries"
                " WHERE data_entry_type_id = ANY(:det_ids) AND id > :after_id"
                " ORDER BY id LIMIT :limit"
            ),
            {
                "det_ids": sorted(RULES_BY_DATA_ENTRY_TYPE),
                "after_id": after_id,
                "limit": _CHUNK,
            },
        )
    ).fetchall()


def _audit_entry(report: Report, row) -> None:
    report.entries_scanned += 1
    det = DataEntryTypeEnum(row.data_entry_type_id)
    data = _as_dict(row.data)
    normalized = normalize_entry_data(det.value, data)
    for key in RULES_BY_DATA_ENTRY_TYPE[det.value]:
        if key not in data:
            continue
        reason = _rejected_reason(det, key, normalized[key])
        if reason is not None:
            report.rejected.append(
                {
                    "id": row.id,
                    "type": det.name,
                    "key": key,
                    "value": data[key],
                    "reason": reason,
                }
            )
        if normalized[key] == data[key]:
            continue
        report.entry_changes[(det.name, key)] += 1
        if row.status == DataEntryStatusEnum.VALIDATED.value:
            report.entry_validated[(det.name, key)] += 1
    if normalized != data:
        report.entry_rewrites[row.id] = normalized


async def audit_entries(conn: AsyncConnection, report: Report) -> None:
    after_id = 0
    while True:
        rows = await _entry_chunk(conn, after_id)
        if not rows:
            return
        for row in rows:
            _audit_entry(report, row)
        after_id = rows[-1].id


async def audit(conn: AsyncConnection) -> Report:
    report = Report()
    await audit_factors(conn, report)
    await audit_entries(conn, report)
    return report


# --------------------------------------------------------------- apply ----


async def apply(conn: AsyncConnection, report: Report) -> None:
    """Rewrite the rows the audit reported. Refuses when factors would collide."""
    if report.duplicate_groups:
        raise ValueError(
            f"{len(report.duplicate_groups)} factor identities collide after"
            " normalization; merge them by hand first (emissions point at them)"
        )
    if report.rejected:
        raise ValueError(
            f"{len(report.rejected)} values need a manual decision; see the report"
        )
    for factor_id, classification in report.factor_rewrites.items():
        await conn.execute(
            text(
                "UPDATE factors SET classification = CAST(:cls AS jsonb) WHERE id = :id"
            ),
            {"cls": json.dumps(classification), "id": factor_id},
        )
    for entry_id, data in report.entry_rewrites.items():
        await conn.execute(
            text("UPDATE data_entries SET data = CAST(:data AS jsonb) WHERE id = :id"),
            {"data": json.dumps(data), "id": entry_id},
        )


# -------------------------------------------------------------- render ----


def render(report: Report) -> str:
    lines = [
        f"Factors scanned: {report.factors_scanned},"
        f" to rewrite: {len(report.factor_rewrites)},"
        f" colliding identities: {len(report.duplicate_groups)}",
    ]
    for (det_name, key), count in sorted(report.factor_changes.items()):
        lines.append(f"  factor {det_name}.{key}: {count}")
    for ids in report.duplicate_groups[:20]:
        lines.append(f"  collide: factor ids {ids}")
    lines += [
        "",
        f"Entries scanned: {report.entries_scanned},"
        f" to rewrite: {len(report.entry_rewrites)}",
        "",
        "| type | key | rows to rewrite | of which validated |",
        "| --- | --- | ---: | ---: |",
    ]
    for (det_name, key), count in sorted(report.entry_changes.items()):
        validated = report.entry_validated[(det_name, key)]
        lines.append(f"| {det_name} | {key} | {count} | {validated} |")
    if not report.entry_changes:
        lines.append("| (none) | | 0 | 0 |")
    lines += ["", f"Values needing a manual decision: {len(report.rejected)}"]
    for item in report.rejected:
        lines.append(
            f"- entry {item['id']} ({item['type']}) {item['key']}={item['value']!r}:"
            f" {item['reason']}"
        )
    return "\n".join(lines)


async def _run(do_apply: bool) -> int:
    async with engine.connect() as conn:
        report = await audit(conn)
    print(render(report))
    if not do_apply:
        return 0
    async with engine.begin() as conn:
        await apply(conn, report)
    print(
        f"\nApplied: {len(report.factor_rewrites)} factors,"
        f" {len(report.entry_rewrites)} entries rewritten"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite the reported rows (default: dry run)",
    )
    args = parser.parse_args()
    load_dotenv()
    return asyncio.run(_run(args.apply))


if __name__ == "__main__":
    sys.exit(main())
