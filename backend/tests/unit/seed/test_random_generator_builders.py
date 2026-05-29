"""Regression smoke test for the Faker seed-data generator (issue #222).

The random generator emits a JSONB payload per ``data_entry`` row. Before this
test existed, payload field names drifted from the Pydantic schemas (e.g.
``active_usage_hours`` vs ``active_usage_hours_per_week``) and only surfaced
when the seeded DB was read by the API. This test runs every builder against
its real create-DTO and asserts validation succeeds — that's the failure mode
the field-drift bug created, so this is the regression net.

The test also asserts the DTO map covers every ``DataEntryTypeEnum`` reachable
via ``MODULE_TYPE_TO_DATA_ENTRY_TYPES``; without that coverage the generator
would KeyError mid-batch for any newly added enum value.
"""

import random

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES
from app.seed.random_generator.populate_units_and_users import NUM_UNITS
from app.seed.random_generator.seed_data_entries import (
    DATA_ENTRY_TYPE_TO_DTO,
    DTO_BUILDERS,
    ENTRIES_PER_MODULE_MAX,
    ENTRIES_PER_MODULE_MIN,
)


@pytest.fixture(autouse=True)
def _seed_rng():
    # Deterministic so a flaky builder can't make the suite pass by luck.
    random.seed(20260528)


@pytest.mark.parametrize("dto_class, builder", list(DTO_BUILDERS.items()))
def test_builder_payload_validates_against_dto(dto_class, builder):
    """Every builder must produce a payload the create-DTO accepts.

    Drives the regression net for field-name drift between the seed
    generator and the Pydantic schemas (issue #222).
    """
    for _ in range(50):
        payload = builder()
        # ``data_entry_type_id`` and ``carbon_report_module_id`` are required
        # meta fields on ``DataEntryCreate``; the seed loop injects them too.
        dto_class(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=1,
            **payload,
        )


def test_dto_map_covers_every_reachable_data_entry_type():
    """The generator picks a random ``data_entry_type`` from whatever
    ``MODULE_TYPE_TO_DATA_ENTRY_TYPES`` returns for the module's type.
    Any uncovered value would raise ``KeyError`` mid-batch in production.
    """
    reachable: set[DataEntryTypeEnum] = set()
    for types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.values():
        reachable.update(types)

    missing = reachable - set(DATA_ENTRY_TYPE_TO_DTO.keys())
    missing_names = sorted(t.name for t in missing)
    assert missing == set(), (
        f"DATA_ENTRY_TYPE_TO_DTO is missing entries for: {missing_names}"
    )


def test_every_dto_in_map_has_a_builder():
    """No silent fallback path: every DTO the map can resolve to must have
    a registered builder, otherwise ``DTO_BUILDERS[dto]`` raises KeyError.
    """
    missing = set(DATA_ENTRY_TYPE_TO_DTO.values()) - set(DTO_BUILDERS.keys())
    assert missing == set(), (
        f"DTO_BUILDERS is missing builders for: {sorted(c.__name__ for c in missing)}"
    )


def test_entries_per_module_window_targets_800k_rows():
    """Document the row-count math as an assertion: with the configured
    NUM_UNITS, YEARS=3, ALL_MODULE_TYPE_IDS=8, the avg total stays in the
    ~800k ±100k band the task targets.
    """
    avg_per_module = (ENTRIES_PER_MODULE_MIN + ENTRIES_PER_MODULE_MAX) / 2
    num_years = 3
    num_module_types = 8
    expected_total = avg_per_module * NUM_UNITS * num_years * num_module_types
    assert 700_000 <= expected_total <= 900_000, (
        f"Expected ~800k ±100k rows; got {expected_total}. "
        f"Adjust ENTRIES_PER_MODULE_MIN/MAX or NUM_UNITS."
    )
