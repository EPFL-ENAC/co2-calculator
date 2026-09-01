"""Re-importing a factor CSV with casing noise keeps one identity (#1489).

The upsert keys on ``(data_entry_type_id, year, emission_type_id,
classification::text)``, so ``_process_row`` must hand ``prepare_create``
the DTO-normalized classification: before the fix it rebuilt the dict from
the raw CSV strings, and a re-import of the same factor with "CHF" instead
of "chf" inserted a second row instead of updating the first.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.services.data_ingestion.base_factor_csv_provider import BaseFactorCSVProvider


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


async def _classification_for(row: dict[str, str]) -> dict:
    det = DataEntryTypeEnum.consumable_accessories
    provider = _Provider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": det.value},
        data_session=MagicMock(),
    )
    provider.year = 2025
    factor_service = MagicMock()
    factor_service.prepare_create = AsyncMock(return_value=MagicMock())
    with patch(
        "app.services.data_ingestion.base_factor_csv_provider"
        ".get_factor_emission_type_id",
        return_value=1,
    ):
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
async def test_same_factor_with_casing_noise_keeps_one_identity():
    canonical = await _classification_for(
        {
            "purchase_institutional_code": "51100000",
            "purchase_additional_code": "",
            "currency": "chf",
            "ef_kg_co2eq_per_currency": "0.41",
        }
    )
    noisy = await _classification_for(
        {
            "purchase_institutional_code": " 51100000 ",
            "purchase_additional_code": "  ",
            "currency": "CHF",
            "ef_kg_co2eq_per_currency": "0.41",
        }
    )
    assert canonical == noisy
    assert canonical == {
        "purchase_institutional_code": "51100000",
        "purchase_additional_code": None,
        "currency": "chf",
        # In classification_fields since #2401 (label translation); absent
        # in the CSV so it stays None.
        "purchase_institutional_description": None,
    }
