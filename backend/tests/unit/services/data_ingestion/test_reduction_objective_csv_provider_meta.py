"""The reduction-objective provider ships row errors in the same meta
shape as the module CSV providers: counts at the root, the list only under
``stats``. Every UI reader looks there (#2464).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.data_ingestion.csv_providers.reduction_objectives import (
    ModulePerYearReductionObjectivesApiProvider,
)


@pytest.mark.asyncio
async def test_finalize_nests_row_errors_under_stats():
    data_session = MagicMock()
    data_session.flush = AsyncMock()
    provider = ModulePerYearReductionObjectivesApiProvider(
        {"file_path": "tmp/test.csv", "year": 2025}, data_session=data_session
    )
    provider._move_to_processed = AsyncMock(return_value="processed/test.csv")
    provider._update_job = AsyncMock()
    stats = {
        "rows_processed": 3,
        "rows_skipped": 1,
        "row_errors": [{"row": 2, "reason": "value: Input should be a number"}],
        "row_errors_count": 1,
    }

    await provider._finalize(stats, {"processing_path": "processing/test.csv"})

    meta = provider._update_job.call_args.kwargs["extra_metadata"]
    assert "row_errors" not in meta
    assert meta["row_errors_count"] == 1
    assert meta["stats"]["row_errors"] == stats["row_errors"]
