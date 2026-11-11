"""Units from a CSV file, for an institution without Accred (#500).

With UNIT_PROVIDER_TYPE=database the unit sync reads UNITS_CSV_PATH, a file
the deployment mounts. One row per unit:

    institutional_code,institutional_id,name,level,parent_institutional_code,label_en,label_fr,is_active

- institutional_code: unique, stable code of the unit.
- institutional_id: the id that the role claims name ("<role>@unit:<id>").
- level: 1 for the root, each child one more than its parent.
- parent_institutional_code: empty for the root.
- label_en, label_fr, is_active: optional. is_active is "true" or "false".

The reader computes the root-to-unit paths from the parent chain. A wrong
file raises ValueError with the row number: a partial unit tree is worse
than a failed sync.
"""

import csv
from pathlib import Path

REQUIRED_COLUMNS = (
    "institutional_code",
    "institutional_id",
    "name",
    "level",
    "parent_institutional_code",
)
_BOOLEANS = {"true": True, "false": False}


def read_units_csv(path: str) -> list[dict]:
    """Read and check the units CSV. Returns one Unit field dict per row."""
    if not path:
        raise ValueError(
            "UNITS_CSV_PATH is not set: a 'database' unit sync reads its units "
            "from this CSV file"
        )
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}")
        rows = {}
        for line, raw in enumerate(reader, start=2):
            row = _parse_row(raw, line)
            if row["institutional_code"] in rows:
                raise ValueError(
                    f"{path} row {line}: duplicate institutional_code "
                    f"{row['institutional_code']!r}"
                )
            rows[row["institutional_code"]] = row
    for row in rows.values():
        _add_paths(row, rows)
    return list(rows.values())


def _parse_row(raw: dict, line: int) -> dict:
    values = {key: (value or "").strip() for key, value in raw.items() if key}
    for column in ("institutional_code", "institutional_id", "name", "level"):
        if not values[column]:
            raise ValueError(f"row {line}: {column} is empty")
    if not values["level"].isdigit() or int(values["level"]) < 1:
        raise ValueError(f"row {line}: level must be a whole number from 1")
    is_active = values.get("is_active") or "true"
    if is_active.lower() not in _BOOLEANS:
        raise ValueError(f"row {line}: is_active must be true or false")
    return {
        "institutional_code": values["institutional_code"],
        "institutional_id": values["institutional_id"],
        "name": values["name"],
        "level": int(values["level"]),
        "parent_institutional_code": values["parent_institutional_code"] or None,
        "label_en": values.get("label_en") or None,
        "label_fr": values.get("label_fr") or None,
        "is_active": _BOOLEANS[is_active.lower()],
        "_line": line,
    }


def _add_paths(row: dict, rows: dict[str, dict]) -> None:
    """Walk up the parent chain and set the root-to-unit paths and parent id."""
    chain = [row]
    while chain[-1]["parent_institutional_code"] is not None:
        parent = rows.get(chain[-1]["parent_institutional_code"])
        if parent is None:
            raise ValueError(
                f"row {chain[-1]['_line']}: parent "
                f"{chain[-1]['parent_institutional_code']!r} is not in the file"
            )
        if parent in chain:
            raise ValueError(f"row {row['_line']}: the parent chain loops")
        if chain[-1]["level"] != parent["level"] + 1:
            raise ValueError(
                f"row {chain[-1]['_line']}: level must be its parent's level + 1"
            )
        chain.append(parent)
    if chain[-1]["level"] != 1:
        raise ValueError(f"row {chain[-1]['_line']}: a unit without parent is level 1")
    path = list(reversed(chain))
    row["path_institutional_code"] = " ".join(u["institutional_code"] for u in path)
    row["path_institutional_id"] = " ".join(u["institutional_id"] for u in path)
    row["path_name"] = " ".join(u["name"] for u in path)
    parent_row = chain[1] if len(chain) > 1 else None
    row["parent_institutional_id"] = (
        parent_row["institutional_id"] if parent_row else None
    )
