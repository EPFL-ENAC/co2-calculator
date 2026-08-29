"""Pins #2161's real per-data_entry_type ceilings against silent drift.

Source: GitHub issue #2161 (2026-08-18); consumed by
scripts/generate_perf_test_csvs.py and the SEED_CEILING_SCALE seeding mode.
"""

from app.models.data_entry import DataEntryTypeEnum
from app.seed.ceilings import CEILING_PER_UNIT_YEAR, TOTAL_CEILING_PER_UNIT_YEAR


def test_ceiling_covers_every_calculator_data_entry_type():
    calculator_types = {t for t in DataEntryTypeEnum if not t.is_planner_kind}
    assert set(CEILING_PER_UNIT_YEAR) == calculator_types


def test_ceiling_values_match_issue_2161():
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.member] == 500
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.train] == 5000
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.animal_facilities] == 50
    assert CEILING_PER_UNIT_YEAR[DataEntryTypeEnum.purchases_centralized] == 1000


def test_total_ceiling_is_pinned():
    assert TOTAL_CEILING_PER_UNIT_YEAR == 21_050
