"""CSV providers reuse the process-wide files store.

A new store per job builds a new S3Service, whose aiobotocore client is
never closed, so aiohttp logs "Unclosed client session" on every job.
"""

from types import SimpleNamespace

import pytest

from app.api.v1 import files
from app.services.data_ingestion.base_csv_provider import BaseCSVProvider
from app.services.data_ingestion.base_factor_csv_provider import (
    BaseFactorCSVProvider,
)
from app.services.data_ingestion.base_reduction_objective_csv_provider import (
    BaseReductionObjectiveCSVProvider,
)
from app.services.data_ingestion.csv_providers.reference_data import (
    ReferenceDataCSVProvider,
)


@pytest.mark.parametrize(
    "provider_cls",
    [
        BaseCSVProvider,
        BaseReductionObjectiveCSVProvider,
        BaseFactorCSVProvider,
        ReferenceDataCSVProvider,
    ],
)
def test_files_store_is_the_shared_singleton(provider_cls: type) -> None:
    first = SimpleNamespace(_files_store=None)
    second = SimpleNamespace(_files_store=None)

    store_a = provider_cls.files_store.fget(first)
    store_b = provider_cls.files_store.fget(second)

    assert store_a is files.files_store
    assert store_b is files.files_store


@pytest.mark.parametrize(
    "provider_cls",
    [
        BaseCSVProvider,
        BaseReductionObjectiveCSVProvider,
        BaseFactorCSVProvider,
        ReferenceDataCSVProvider,
    ],
)
def test_patching_the_shared_store_reaches_providers(
    provider_cls: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = object()
    monkeypatch.setattr(files, "files_store", fake)

    assert provider_cls.files_store.fget(SimpleNamespace(_files_store=None)) is fake
