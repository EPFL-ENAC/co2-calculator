"""``CarbonReportService.compare_years`` — the SQL fold behind Compare Years."""

import pytest

from app.services.carbon_report_service import CarbonReportService


def _stats(buckets: dict[str, tuple[float, int]], validated: list[str]) -> dict:
    return {
        "buckets": {
            key: {"total_kg": kg, "scope": scope}
            for key, (kg, scope) in buckets.items()
        },
        "validated_buckets": validated,
    }


@pytest.mark.asyncio
async def test_buckets_to_tonnes_by_module_and_scope(db_session, make_carbon_report):
    await make_carbon_report(
        db_session,
        unit_id=1,
        year=2025,
        stats=_stats(
            {
                "buildings_energy_combustion": (150.0, 1),
                "buildings_room": (30.0, 2),
                "commuting": (5.0, 3),
                "food": (20.0, 3),
                "embodied_energy": (7.0, 3),
                "equipment": (1000.0, 2),
            },
            validated=[
                "buildings_energy_combustion",
                "buildings_room",
                "commuting",
                "food",
                "embodied_energy",
            ],
        ),
    )

    (entry,) = await CarbonReportService(db_session).compare_years([1])

    assert entry["year"] == 2025
    assert entry["modules"] == {
        "buildings_energy_combustion": 0.150,
        "buildings_room": 0.030,
        "commuting": 0.005,
        "food": 0.020,
        "embodied_energy": 0.007,
    }
    assert entry["scopes"] == {"1": 0.150, "2": 0.030, "3": 0.032}
    assert entry["total_tonnes_co2eq"] == pytest.approx(0.212)


@pytest.mark.asyncio
async def test_skips_non_positive_and_unvalidated_buckets(
    db_session, make_carbon_report
):
    await make_carbon_report(
        db_session,
        unit_id=1,
        year=2025,
        stats=_stats(
            {
                "equipment": (0.0, 2),
                "purchases": (-5.0, 3),
                "food": (1000.0, 3),
                "professional_travel": (500.0, 3),
            },
            validated=["equipment", "purchases", "food"],
        ),
    )

    (entry,) = await CarbonReportService(db_session).compare_years([1])

    assert entry["modules"] == {"food": 1.0}
    assert entry["scopes"] == {"1": 0.0, "2": 0.0, "3": 1.0}
    assert entry["total_tonnes_co2eq"] == 1.0


@pytest.mark.asyncio
async def test_sums_units_per_year_and_orders_years(db_session, make_carbon_report):
    await make_carbon_report(
        db_session, unit_id=1, year=2026, stats=_stats({"food": (100.0, 3)}, ["food"])
    )
    await make_carbon_report(
        db_session, unit_id=2, year=2026, stats=_stats({"food": (300.0, 3)}, ["food"])
    )
    await make_carbon_report(
        db_session, unit_id=1, year=2025, stats=_stats({"food": (50.0, 3)}, ["food"])
    )
    await make_carbon_report(
        db_session, unit_id=3, year=2026, stats=_stats({"food": (999.0, 3)}, ["food"])
    )

    years = await CarbonReportService(db_session).compare_years([1, 2])

    assert [y["year"] for y in years] == [2025, 2026]
    assert years[1]["modules"] == {"food": 0.4}
    assert years[0]["modules"] == {"food": 0.05}


@pytest.mark.asyncio
async def test_validated_in_any_unit_counts_whole_year(db_session, make_carbon_report):
    await make_carbon_report(
        db_session, unit_id=1, year=2026, stats=_stats({"food": (100.0, 3)}, ["food"])
    )
    await make_carbon_report(
        db_session, unit_id=2, year=2026, stats=_stats({"food": (300.0, 3)}, [])
    )

    (entry,) = await CarbonReportService(db_session).compare_years([1, 2])

    assert entry["modules"] == {"food": 0.4}


@pytest.mark.asyncio
async def test_no_reports_or_no_stats_yields_empty(db_session, make_carbon_report):
    await make_carbon_report(db_session, unit_id=1, year=2026, stats=None)

    assert await CarbonReportService(db_session).compare_years([1]) == []
    assert await CarbonReportService(db_session).compare_years([7]) == []
