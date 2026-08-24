"""#2007 — say which filter emptied the ingest, and whether that is a fault.

A 2026 research-facilities sync failed with "No research facilities rows
passed validation — all rows were filtered out during transform", which reads
like a validation bug. It wasn't: all 9484 rows the datasource returned were
dated 2025. The message could not distinguish "this year isn't published yet"
from "the datasource changed shape", and answering it took a one-off probe.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_ingestion import IngestionResult, IngestionState
from app.services.data_ingestion.api_providers.research_facilities_api_provider import (
    ResearchFacilitiesApiProvider,
)

USE_KEY = "SUM(amount)"


def _row(**overrides) -> dict:
    return {
        "client_type": "INTERNE",
        "date_iso": "20251126",
        "research_facility_id": "1901",
        "research_facility_name": "AVP-E-CEDE",
        "unit_institutional_id": "0040",
        USE_KEY: -1367.0,
        **overrides,
    }


def _provider(year: int) -> ResearchFacilitiesApiProvider:
    provider = ResearchFacilitiesApiProvider(
        config={"year": year, "data_entry_type_id": 70},
        data_session=MagicMock(),
    )
    provider._update_job = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_transform_tallies_each_filter_separately():
    provider = _provider(2026)

    await provider.transform_data(
        [
            _row(),  # 2025 → wrong year
            _row(),
            _row(client_type="EXTERNE"),
            _row(date_iso="20260301", research_facility_id="  "),
            _row(date_iso="20260301", research_facility_name=""),
            _row(date_iso="20260301", **{USE_KEY: None}),
            _row(date_iso="20260301", **{USE_KEY: "n/a"}),
            _row(date_iso="20260301", **{USE_KEY: 500.0}),
        ]
    )

    assert dict(provider.drop_reasons) == {
        "year": 2,
        "client_type": 1,
        "blank_id": 1,
        "blank_name": 1,
        "no_amount": 1,
        "amount_not_numeric": 1,
        "amount_positive": 1,
    }


@pytest.mark.asyncio
async def test_the_2026_incident_is_a_warning_naming_the_year():
    """The reported case: every row is real, in-scope billing for 2025."""
    provider = _provider(2026)
    rows = [_row() for _ in range(8916)] + [
        _row(client_type="EXTERNE") for _ in range(568)
    ]

    transformed = await provider.transform_data(rows)
    assert transformed == []

    outcome = await provider._finalize_empty_transform(len(rows))

    assert outcome["result"] is IngestionResult.WARNING
    assert outcome["state"] is IngestionState.FINISHED
    assert outcome["skipped"] == 9484
    # Both filters named with their tallies, so nobody has to guess again.
    assert (
        "8916 row(s) are dated a different year than 2026" in outcome["status_message"]
    )
    assert "568 row(s) are not internal billing" in outcome["status_message"]
    # The old wording blamed the data; this one does not.
    assert "passed validation" not in outcome["status_message"]


@pytest.mark.asyncio
async def test_an_anomalous_filter_still_fails_loudly():
    """A flipped sign convention would empty the ingest just as completely —
    that one is a fault and must keep raising.
    """
    provider = _provider(2025)
    rows = [_row(**{USE_KEY: 1367.0}) for _ in range(9484)]

    assert await provider.transform_data(rows) == []

    with pytest.raises(ValueError) as exc_info:
        await provider._finalize_empty_transform(len(rows))

    message = str(exc_info.value)
    assert "9484 row(s) have a positive SUM(amount)" in message
    assert "internal billing is recorded negative" in message
    assert "contact the Tableau team" in message


@pytest.mark.asyncio
async def test_a_mix_of_routine_and_anomalous_still_fails():
    """Routine exclusions must not launder an anomaly into a warning."""
    provider = _provider(2026)
    rows = [_row() for _ in range(10)] + [_row(date_iso="20260301", **{USE_KEY: 5.0})]

    assert await provider.transform_data(rows) == []

    with pytest.raises(ValueError, match="positive"):
        await provider._finalize_empty_transform(len(rows))


@pytest.mark.asyncio
async def test_in_scope_rows_are_kept_and_negated():
    provider = _provider(2025)

    transformed = await provider.transform_data([_row(), _row(client_type="EXTERNE")])

    assert provider.drop_reasons == {"client_type": 1}
    assert transformed == [
        {
            "unit_institutional_id": "0040",
            "researchfacility_id": "1901",
            "researchfacility_name": "AVP-E-CEDE",
            "use": 1367.0,
            "use_unit": "CHF",
            "note": None,
        }
    ]


@pytest.mark.asyncio
async def test_ingest_short_circuits_before_touching_existing_entries():
    """An empty fetch is not evidence that an earlier sync's rows are stale."""
    provider = _provider(2026)
    provider.fetch_data = AsyncMock(return_value=[_row()])
    provider._report_progress = AsyncMock()
    provider._delete_existing_api_entries = AsyncMock()
    provider._load_data = AsyncMock()
    provider._resolve_carbon_report_modules = AsyncMock(
        side_effect=AssertionError("must not resolve modules for an empty transform")
    )

    outcome = await provider.ingest({})

    assert outcome["result"] is IngestionResult.WARNING
    provider._delete_existing_api_entries.assert_not_called()
    provider._load_data.assert_not_called()


@pytest.mark.asyncio
async def test_a_datasource_returning_nothing_is_left_to_the_existing_path():
    """Zero fetched rows is not a filtering story — no drop reasons to report,
    so the pre-existing resolution error still owns it.
    """
    provider = _provider(2026)
    provider.fetch_data = AsyncMock(return_value=[])
    provider._report_progress = AsyncMock()
    provider._resolve_carbon_report_modules = AsyncMock(
        side_effect=ValueError("No research facilities rows passed validation")
    )

    with pytest.raises(ValueError, match="passed validation"):
        await provider.ingest({})

    assert not provider.drop_reasons
