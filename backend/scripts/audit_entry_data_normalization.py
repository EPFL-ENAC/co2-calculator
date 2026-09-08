"""Read-only audit of what migration cf237968fba7 (#2592) would rewrite.

Counts, per data entry type and key, the ``data_entries`` rows whose join
keys are not in the DTO-normalized form yet, how many of those are validated
entries, and lists values the vocabulary checks would reject after
normalization (a currency outside the supported list, an unknown cabin class,
a malformed country code). Those need a manual decision, not a bulk rewrite.

    uv run python -m scripts.audit_entry_data_normalization

Uses the migration's own rules (imported from the migration file) so the
report describes exactly what the migration does. Never writes.
"""

import argparse
import asyncio
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

from dotenv import load_dotenv
from sqlalchemy import text

from app.db import engine
from app.models.data_entry import DataEntryStatusEnum, DataEntryTypeEnum
from app.modules.professional_travel.emissions import (
    PLANE_CABIN_MAP,
    TRAIN_CLASS_MAP,
)
from app.schemas.fields import ROW_COUNTRY_CODE
from app.utils.currencies import SUPPORTED_CURRENCIES

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "2026_09_08_1029-cf237968fba7_normalize_entry_data_join_keys.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "migration_cf237968fba7", _MIGRATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration module at {_MIGRATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


async def _fetch_rows(det_ids: list[int]) -> list[tuple[int, int, int | None, dict]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, data_entry_type_id, status, data FROM data_entries"
                " WHERE data_entry_type_id = ANY(:det_ids)"
            ),
            {"det_ids": det_ids},
        )
        rows = []
        for row in result:
            data = row.data
            if isinstance(data, str):
                data = json.loads(data)
            rows.append((row.id, row.data_entry_type_id, row.status, data or {}))
        return rows


async def audit() -> dict:
    migration = load_migration()
    rules_by_det = migration.RULES_BY_DATA_ENTRY_TYPE
    changed: Counter[tuple[str, str]] = Counter()
    validated: Counter[tuple[str, str]] = Counter()
    rejected: list[dict] = []
    rows = await _fetch_rows(sorted(rules_by_det))
    for entry_id, det_id, status, data in rows:
        det = DataEntryTypeEnum(det_id)
        normalized = migration.normalize_entry_data(det_id, data)
        for key, rule in rules_by_det[det_id].items():
            if key not in data:
                continue
            reason = _rejected_reason(det, key, normalized[key])
            if reason is not None:
                rejected.append(
                    {
                        "id": entry_id,
                        "type": det.name,
                        "key": key,
                        "value": data[key],
                        "reason": reason,
                    }
                )
            if normalized[key] == data[key]:
                continue
            changed[(det.name, key)] += 1
            if status == DataEntryStatusEnum.VALIDATED.value:
                validated[(det.name, key)] += 1
    return {
        "rows_scanned": len(rows),
        "changed": changed,
        "validated": validated,
        "rejected": rejected,
    }


def render(report: dict) -> str:
    lines = [
        f"Rows scanned: {report['rows_scanned']}",
        "",
        "| type | key | rows to rewrite | of which validated |",
        "| --- | --- | ---: | ---: |",
    ]
    for (det_name, key), count in sorted(report["changed"].items()):
        lines.append(
            f"| {det_name} | {key} | {count} | {report['validated'][(det_name, key)]} |"
        )
    if not report["changed"]:
        lines.append("| (none) | | 0 | 0 |")
    lines += ["", f"Values needing a manual decision: {len(report['rejected'])}"]
    for item in report["rejected"]:
        lines.append(
            f"- entry {item['id']} ({item['type']}) "
            f"{item['key']}={item['value']!r}: {item['reason']}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    load_dotenv()
    print(render(asyncio.run(audit())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
