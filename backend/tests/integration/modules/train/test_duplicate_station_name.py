"""Regression test: pre_compute must not raise MultipleResultsFound when two
train stations share the same name but differ by country_code.

Bug: get_by_name() used scalar_one_or_none() on a query that returned
multiple rows (e.g. "Berne CH" and "Berne DE"), raising
sqlalchemy.exc.MultipleResultsFound → 500.

Fix: transport_mode is now required in get_by_name(), so cross-mode
ambiguity is impossible. MultipleResultsFound (same mode, same name,
different country) is caught and returns None → pre_compute returns {}.
"""

import types

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.location import Location, TransportModeEnum
from app.modules.professional_travel.schemas import (
    ProfessionalTravelTrainModuleHandler,
)


def _make_data_entry(data: dict):
    """Minimal data-entry stub — pre_compute only calls data_entry.data.get(...)."""
    entry = types.SimpleNamespace()
    entry.data = data
    return entry


@pytest.mark.asyncio
async def test_pre_compute_resolves_duplicate_station_name_by_country(
    db_session: AsyncSession,
):
    """pre_compute returns correctly resolved country_code when two stations
    share the same name but have different country_codes.

    Without the fix this raises sqlalchemy.exc.MultipleResultsFound.
    """
    # ── seed two "Berne" stations ────────────────────────────────────────
    berne_ch = Location(
        name="Berne",
        transport_mode=TransportModeEnum.train,
        country_code="CH",
        latitude=46.9481,
        longitude=7.4474,
    )
    berne_de = Location(
        name="Berne",
        transport_mode=TransportModeEnum.train,
        country_code="DE",
        latitude=52.5200,
        longitude=13.4050,
    )
    db_session.add(berne_ch)
    db_session.add(berne_de)
    await db_session.flush()

    # ── call pre_compute with country codes ──────────────────────────────
    handler = ProfessionalTravelTrainModuleHandler()
    data_entry = _make_data_entry(
        {
            "origin_name": "Berne",
            "origin_country_code": "DE",
            "destination_name": "Berne",
            "destination_country_code": "CH",
            "number_of_trips": 1,
        }
    )

    result = await handler.pre_compute(data_entry, db_session)

    # ── assertions ───────────────────────────────────────────────────────
    assert result != {}, (
        "pre_compute returned empty dict — location lookup failed unexpectedly"
    )
    assert "country_code" in result, f"country_code missing from result: {result}"
    # origin=DE, dest=CH → _determine_train_countrycode prefers non-CH (origin DE)
    assert result["country_code"] == "DE", (
        f"Expected country_code='DE' (origin's non-CH country), "
        f"got {result['country_code']!r}"
    )
    assert "distance_km" in result
    assert result["distance_km"] > 0


@pytest.mark.asyncio
async def test_pre_compute_without_country_code_returns_empty_on_ambiguous(
    db_session: AsyncSession,
):
    """Without country_code, pre_compute returns {} when two same-mode stations
    share the same name — MultipleResultsFound is caught in the repo layer and
    the lookup returns None, so pre_compute returns {} instead of raising 500.
    """
    berne_ch = Location(
        name="Ambiguous",
        transport_mode=TransportModeEnum.train,
        country_code="CH",
        latitude=46.9481,
        longitude=7.4474,
    )
    berne_de = Location(
        name="Ambiguous",
        transport_mode=TransportModeEnum.train,
        country_code="DE",
        latitude=52.5200,
        longitude=13.4050,
    )
    db_session.add(berne_ch)
    db_session.add(berne_de)
    await db_session.flush()

    handler = ProfessionalTravelTrainModuleHandler()
    data_entry = _make_data_entry(
        {
            "origin_name": "Ambiguous",
            # No country codes — simulates old/broken frontend payload
            "destination_name": "Ambiguous",
            "number_of_trips": 1,
        }
    )

    result = await handler.pre_compute(data_entry, db_session)

    # Ambiguous lookup returns None → pre_compute short-circuits to {}
    assert result == {}, f"Expected empty dict for ambiguous lookup, got: {result}"
