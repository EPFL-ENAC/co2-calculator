"""CSV providers reuse the process-wide files store.

A new store per job builds a new S3Service, whose aiobotocore client is
never closed, so aiohttp logs "Unclosed client session" on every job.
"""

from types import SimpleNamespace

import pytest

from app.api.v1 import files
from app.services.data_ingestion.base_csv_provider import BaseCSVProvider
from app.services.data_ingestion.base_reduction_objective_csv_provider import (
    BaseReductionObjectiveCSVProvider,
)


@pytest.mark.parametrize(
    "provider_cls", [BaseCSVProvider, BaseReductionObjectiveCSVProvider]
)
def test_files_store_is_the_shared_singleton(provider_cls: type) -> None:
    first = SimpleNamespace(_files_store=None)
    second = SimpleNamespace(_files_store=None)

    store_a = provider_cls.files_store.fget(first)
    store_b = provider_cls.files_store.fget(second)

    assert store_a is files.files_store
    assert store_b is files.files_store
