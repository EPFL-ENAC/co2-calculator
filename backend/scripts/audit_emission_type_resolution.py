"""Dry-run every factor CSV in a directory through emission-type resolution.

Since #2091 an unmappable emission type aborts the whole factor upload, so
run this against a batch *before* handing it to the back-office and you
find out in one second instead of one rejected job.

    uv run python scripts/audit_emission_type_resolution.py INPUT_DATA

Exit code is 0 when every row lands on a declared node, 1 otherwise.
Reads the CSVs only — it never touches the database.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions.registry import resolve_factor_emission_type
from app.modules.emissions.taxonomy import EmissionTypeResolutionError
from app.schemas.factor import BaseFactorHandler

# Which data entry type a factor CSV carries. Files whose rows each name
# their own type (via the handler's category_field) are in CATEGORY_DRIVEN.
FIXED_TYPE_BY_FILE: dict[str, DataEntryTypeEnum] = {
    "building_energycombustions_factors.csv": DataEntryTypeEnum.energy_combustion,
    "building_rooms_factors.csv": DataEntryTypeEnum.building,
    "buildings_construction_renovation_factors.csv": (
        DataEntryTypeEnum.building_embodied_energy
    ),
    "external_ai_factors.csv": DataEntryTypeEnum.external_ai,
    "external_clouds_factors.csv": DataEntryTypeEnum.external_clouds,
    "headcount_member_factors.csv": DataEntryTypeEnum.member,
    "headcount_students_factors.csv": DataEntryTypeEnum.student,
    "processemissions_factors.csv": DataEntryTypeEnum.process_emissions,
    "purchases_centralized_factors.csv": DataEntryTypeEnum.purchases_centralized,
    "researchfacilities_animals_factors.csv": DataEntryTypeEnum.animal_facilities,
    "researchfacilities_common_factors.csv": DataEntryTypeEnum.research_facilities,
    "travel_planes_factors.csv": DataEntryTypeEnum.plane,
    "travel_trains_factors.csv": DataEntryTypeEnum.train,
}

CATEGORY_DRIVEN_BY_FILE: dict[str, str] = {
    "equipment_factors.csv": "equipment_category",
    "purchases_common_factors.csv": "purchase_category",
}


def _data_entry_type(file_name: str, row: dict) -> DataEntryTypeEnum | None:
    if file_name in FIXED_TYPE_BY_FILE:
        return FIXED_TYPE_BY_FILE[file_name]
    category_field = CATEGORY_DRIVEN_BY_FILE[file_name]
    try:
        return DataEntryTypeEnum[(row.get(category_field) or "").strip()]
    except KeyError:
        return None


def _audit_file(path: Path) -> list[str]:
    """Return one message per row that would abort the upload."""
    failures: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row_idx, row in enumerate(csv.DictReader(handle), start=2):
            data_entry_type = _data_entry_type(path.name, row)
            if data_entry_type is None:
                failures.append(f"row {row_idx}: unknown category column value")
                continue
            handler = BaseFactorHandler.get_by_type(data_entry_type)
            classification = {
                field: (row.get(field) or "").strip() or None
                for field in handler.classification_fields
            }
            try:
                resolve_factor_emission_type(data_entry_type, classification)
            except EmissionTypeResolutionError as error:
                failures.append(f"row {row_idx}: {error}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="directory of factor CSVs")
    args = parser.parse_args()

    known = set(FIXED_TYPE_BY_FILE) | set(CATEGORY_DRIVEN_BY_FILE)
    totals: Counter[str] = Counter()
    for path in sorted(args.directory.glob("*factors*.csv")):
        if path.name not in known:
            print(f"{path.name}: skipped (not a known factor CSV)")
            continue
        failures = _audit_file(path)
        totals["files"] += 1
        totals["failures"] += len(failures)
        status = "OK" if not failures else f"{len(failures)} row(s) would abort"
        print(f"{path.name}: {status}")
        for message in failures[:20]:
            print(f"    {message}")
        if len(failures) > 20:
            print(f"    ... and {len(failures) - 20} more")

    print(f"\n{totals['files']} file(s), {totals['failures']} blocking row(s)")
    return 1 if totals["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
