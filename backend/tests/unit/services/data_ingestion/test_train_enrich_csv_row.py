"""Unit tests for the train CSV enrichment hook's country_code requirement.

Issue #1183: train CSV ingestion now *requires* a ``{role}_country_code`` for
any row that does not already carry a ``{role}_natural_key``. There is no more
``CH`` default — a row missing the country code is rejected before any station
lookup, so the operator must supply it (the new ``stations.csv``-derived seed
ships country codes natively).
"""

from unittest.mock import MagicMock

import pytest

from app.modules.professional_travel.schemas import (
    ProfessionalTravelTrainModuleHandler,
)


class _ForbiddenSession:
    """Sentinel session: any attribute access means the resolver wrongly
    reached the DB instead of rejecting the row on the missing country_code."""

    def __getattr__(self, name: str):
        raise AssertionError(
            f"station lookup must not run when country_code is missing "
            f"(accessed session.{name})"
        )


@pytest.mark.asyncio
async def test_train_enrich_requires_origin_country_code() -> None:
    handler = ProfessionalTravelTrainModuleHandler()
    data = {
        "origin_name": "Berne",
        "destination_name": "Geneva",
        "destination_country_code": "CH",
        # origin_country_code intentionally absent
    }

    enriched, err = await handler.enrich_csv_row(data, _ForbiddenSession())

    assert err is not None
    assert "origin_country_code" in err
    assert "origin_natural_key" not in enriched


@pytest.mark.asyncio
async def test_train_enrich_requires_destination_country_code() -> None:
    handler = ProfessionalTravelTrainModuleHandler()
    data = {
        # origin already resolved (UI/API path) → skipped, no lookup
        "origin_name": "Geneva",
        "origin_natural_key": "train:ch:geneva:46.2104:6.1428",
        "destination_name": "Berne",
        # destination_country_code intentionally absent
    }

    enriched, err = await handler.enrich_csv_row(data, _ForbiddenSession())

    assert err is not None
    assert "destination_country_code" in err
    assert "destination_natural_key" not in enriched


@pytest.mark.asyncio
async def test_train_enrich_normalizes_country_code_case_for_lookup(
    monkeypatch,
) -> None:
    """The seed stores ISO-2 country codes uppercase (``FR``) and the station
    lookup matches ``country_code`` exactly, so the resolver must canonicalize
    the CSV value to uppercase — otherwise a lowercase ``de`` silently fails
    to resolve and the row persists without emission."""
    captured: dict[str, str] = {}

    class _FakeStation:
        natural_key = "train:xx:fake:0.0:0.0"

    async def _fake_resolve(self, name: str, country_code: str):
        captured[name] = country_code
        return _FakeStation(), "ok"

    monkeypatch.setattr(
        "app.modules.professional_travel.schemas."
        "LocationService.resolve_train_station_for_csv",
        _fake_resolve,
    )

    handler = ProfessionalTravelTrainModuleHandler()
    data = {
        "origin_name": "Berne",
        "origin_country_code": "de",
        "destination_name": "Geneva",
        "destination_country_code": "ch",
    }

    _, err = await handler.enrich_csv_row(data, MagicMock())

    assert err is None
    assert captured["Berne"] == "DE"
    assert captured["Geneva"] == "CH"
