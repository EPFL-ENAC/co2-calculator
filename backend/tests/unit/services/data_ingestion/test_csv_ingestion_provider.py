"""Tests for CSVIngestionProvider, the shared CSV staging step (#6523).

Every CSV provider (factors, data-entry, reduction-objectives, reference
data) inherits ``_download_and_decode_csv`` from here instead of
duplicating it — this is the single place a BOM-decode fix now needs to
land for all of them to pick it up.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.data_ingestion.csv_ingestion_provider import CSVIngestionProvider


class _ConcreteCSVProvider(CSVIngestionProvider):
    """Minimal concrete subclass — only exists to exercise the shared mixin."""

    @property
    def files_store(self) -> Any:
        return self._files_store

    async def validate_connection(self) -> bool:
        return True

    async def fetch_data(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def transform_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return raw_data

    async def _load_data(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        return {"inserted": 0, "skipped": 0, "errors": 0}


def _build_provider() -> _ConcreteCSVProvider:
    provider = _ConcreteCSVProvider({}, data_session=MagicMock())
    provider.job_id = 1
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=True)
    return provider


@pytest.mark.asyncio
async def test_download_and_decode_csv_strips_utf8_bom():
    provider = _build_provider()
    provider._files_store.get_file = AsyncMock(
        return_value=(b"\xef\xbb\xbfcol1,col2\nval1,val2\n", "text/csv")
    )

    csv_text, processing_path, filename = await provider._download_and_decode_csv(
        "tmp/equipment_factors.csv"
    )

    assert csv_text.startswith("col1,col2")
    assert processing_path == "processing/1/equipment_factors.csv"
    assert filename == "equipment_factors.csv"


@pytest.mark.asyncio
async def test_download_and_decode_csv_no_bom_unaffected():
    provider = _build_provider()
    provider._files_store.get_file = AsyncMock(
        return_value=(b"col1,col2\nval1,val2\n", "text/csv")
    )

    csv_text, _, _ = await provider._download_and_decode_csv("tmp/plain.csv")

    assert csv_text == "col1,col2\nval1,val2\n"


@pytest.mark.asyncio
async def test_download_and_decode_csv_missing_path_raises():
    provider = _build_provider()

    with pytest.raises(ValueError, match="Missing file_path"):
        await provider._download_and_decode_csv(None)


@pytest.mark.asyncio
async def test_download_and_decode_csv_rejects_disallowed_prefix():
    provider = _build_provider()

    with pytest.raises(ValueError, match="Invalid file_path"):
        await provider._download_and_decode_csv("etc/passwd")
