"""Every shipped factor CSV keeps one identity under casing/whitespace noise.

Re-importing a factor file whose cells picked up spaces, a different casing
on a closed-vocabulary key (currency, cabin class, country code, energy
type) or a spreadsheet ``1.0`` on a numeric id must produce the exact same
classification as the clean file, otherwise the upsert (keyed on
``classification::text``) inserts a second row (#1489). Running every row
through the real ``_process_row`` also pins the closed vocabularies
(#2588) against the data the back-office actually uploads.

The committed smoke fixture always runs. The developer-supplied files in
``backend/INPUT_DATA`` (gitignored) run when present.
"""

import re
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.services.data_ingestion.base_factor_csv_provider import BaseFactorCSVProvider
from app.utils.csv_dialect import csv_dict_reader
from scripts.audit_emission_type_resolution import (
    CATEGORY_DRIVEN_BY_FILE,
    FIXED_TYPE_BY_FILE,
)

_BACKEND = Path(__file__).resolve().parents[4]
_INPUT_DATA = _BACKEND / "INPUT_DATA"
_SMOKE = _BACKEND / "tests" / "fixtures" / "csv" / "purchases_common_factors_smoke.csv"

_UPPER_KEYS = {"currency", "cabin_class", "country_code", "energy_type"}
_NUMERIC_ID_KEYS = {"researchfacility_id", "researchfacility_name"}
_INTEGER = re.compile(r"^\d+$")


class _Provider(BaseFactorCSVProvider):
    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_context(self):
        return {}


def _stats():
    return {
        "rows_processed": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
        "factors_deleted": 0,
        "factors_upserted": 0,
    }


def _shipped_files() -> list[Path]:
    files = [_SMOKE]
    if _INPUT_DATA.is_dir():
        files += sorted(_INPUT_DATA.glob("*_factors.csv"))
    return files


def _data_entry_type(file_name: str, row: dict[str, str]) -> DataEntryTypeEnum:
    lookup_name = file_name.replace("_smoke", "")
    if lookup_name in FIXED_TYPE_BY_FILE:
        return FIXED_TYPE_BY_FILE[lookup_name]
    return DataEntryTypeEnum[row[CATEGORY_DRIVEN_BY_FILE[lookup_name]].strip()]


def _noisy(row: dict[str, str]) -> dict[str, str]:
    noisy: dict[str, str] = {}
    for key, value in row.items():
        cell = f"  {value}  " if value else value
        if key in _UPPER_KEYS:
            cell = cell.upper()
        if key in _NUMERIC_ID_KEYS and _INTEGER.match(value or ""):
            cell = f" {value}.0 "
        noisy[key] = cell
    return noisy


async def _classification(provider: _Provider, det: DataEntryTypeEnum, row: dict):
    factor_service = MagicMock()
    factor_service.prepare_create = AsyncMock(return_value=MagicMock())
    factor, error = await provider._process_row(
        row=row,
        row_idx=1,
        setup_result={"handlers": [], "valid_entry_types": [det]},
        stats=_stats(),
        max_row_errors=5,
        factor_service=factor_service,
    )
    assert error is None, error
    assert factor is not None
    return factor_service.prepare_create.call_args.kwargs["classification"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _shipped_files(), ids=lambda p: p.name)
async def test_shipped_factor_csv_rows_keep_identity_under_noise(path: Path) -> None:
    rows_by_det: dict[DataEntryTypeEnum, list[dict[str, str]]] = defaultdict(list)
    text = path.read_bytes().decode("utf-8-sig")
    for row in csv_dict_reader(text):
        rows_by_det[_data_entry_type(path.name, row)].append(row)
    assert rows_by_det, f"{path.name} has no rows"

    with patch(
        "app.services.data_ingestion.base_factor_csv_provider"
        ".get_factor_emission_type_id",
        return_value=1,
    ):
        for det, rows in rows_by_det.items():
            provider = _Provider(
                {"file_path": "tmp/test.csv", "data_entry_type_id": det.value},
                data_session=MagicMock(),
            )
            provider.year = 2025
            for row in rows:
                clean = await _classification(provider, det, row)
                noisy = await _classification(provider, det, _noisy(row))
                assert clean == noisy, f"{path.name} row {row} lost its identity"
