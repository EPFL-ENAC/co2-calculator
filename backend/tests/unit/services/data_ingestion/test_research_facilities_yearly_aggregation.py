"""#924 — SUM(amount) must be a yearly total, not a per-month one.

VDS groups SUM(amount) by every non-aggregated output field in the query,
including date_iso, so the datasource returns one summed row per facility
per month. date_iso is a string-typed calculated field, so it can't be
coerced to a year grain via a VDS field function (rejected: "wrong type
for Function YEAR") nor filtered on without also being an output field
(rejected: "field not defined") — transform_data collapses the monthly
rows into one annual total per facility itself.
"""

from unittest.mock import MagicMock

import pytest

from app.services.data_ingestion.api_providers.research_facilities_api_provider import (
    ResearchFacilitiesApiProvider,
)

USE_KEY = "SUM(amount)"


def _row(**overrides) -> dict:
    return {
        "client_type": "INTERNE",
        "date_iso": "20260101",
        "research_facility_id": "1901",
        "research_facility_name": "AVP-E-CEDE",
        "unit_institutional_id": "0040",
        USE_KEY: -100.0,
        **overrides,
    }


def _provider(year: int) -> ResearchFacilitiesApiProvider:
    return ResearchFacilitiesApiProvider(
        config={"year": year, "data_entry_type_id": 70},
        data_session=MagicMock(),
    )


@pytest.mark.asyncio
async def test_monthly_rows_for_one_facility_are_summed_into_one_yearly_total():
    provider = _provider(2026)

    transformed = await provider.transform_data(
        [
            _row(date_iso="20260101", **{USE_KEY: -100.0}),
            _row(date_iso="20260201", **{USE_KEY: -50.0}),
            _row(date_iso="20261201", **{USE_KEY: -25.5}),
        ]
    )

    assert transformed == [
        {
            "unit_institutional_id": "0040",
            "researchfacility_id": "1901",
            "researchfacility_name": "AVP-E-CEDE",
            "use": 175.5,
            "use_unit": "CHF",
            "note": None,
        }
    ]


@pytest.mark.asyncio
async def test_different_facilities_stay_separate_totals():
    provider = _provider(2026)

    transformed = await provider.transform_data(
        [
            _row(research_facility_id="1901", **{USE_KEY: -100.0}),
            _row(research_facility_id="1901", date_iso="20260201", **{USE_KEY: -50.0}),
            _row(research_facility_id="2002", research_facility_name="OTHER-FAC"),
        ]
    )

    totals = {row["researchfacility_id"]: row["use"] for row in transformed}
    assert totals == {"1901": 150.0, "2002": 100.0}


@pytest.mark.asyncio
async def test_same_facility_id_under_different_units_stays_separate():
    """A facility id is only unique within a unit — don't cross-sum across
    units that happen to share a facility id.
    """
    provider = _provider(2026)

    transformed = await provider.transform_data(
        [
            _row(unit_institutional_id="0040", **{USE_KEY: -100.0}),
            _row(unit_institutional_id="0041", **{USE_KEY: -30.0}),
        ]
    )

    totals = {row["unit_institutional_id"]: row["use"] for row in transformed}
    assert totals == {"0040": 100.0, "0041": 30.0}


@pytest.mark.asyncio
async def test_rows_outside_the_target_year_are_excluded_from_the_total():
    provider = _provider(2026)

    transformed = await provider.transform_data(
        [
            _row(date_iso="20260301", **{USE_KEY: -100.0}),
            _row(date_iso="20251231", **{USE_KEY: -9999.0}),  # wrong year
        ]
    )

    assert transformed == [
        {
            "unit_institutional_id": "0040",
            "researchfacility_id": "1901",
            "researchfacility_name": "AVP-E-CEDE",
            "use": 100.0,
            "use_unit": "CHF",
            "note": None,
        }
    ]
