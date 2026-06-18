"""Unit tests for plane cabin-class → EmissionType resolution.

Verifies that ``_resolve_plane`` (used by ``resolve_emission_types`` at
runtime) correctly maps each cabin class to its EmissionType leaf, and
that unknown or missing values return ``None`` (no emission produced).
"""

import pytest

from app.models.data_entry_emission import EmissionType
from app.utils.data_entry_emission_type_map import _resolve_plane


@pytest.mark.parametrize(
    "cabin_class, expected",
    [
        ("economy", EmissionType.professional_travel__plane__eco),
        ("ECONOMY", EmissionType.professional_travel__plane__eco),
        ("business", EmissionType.professional_travel__plane__business),
        ("Business", EmissionType.professional_travel__plane__business),
        ("first", EmissionType.professional_travel__plane__first),
        ("First", EmissionType.professional_travel__plane__first),
    ],
)
def test_resolve_plane_maps_class_to_emission_type(
    cabin_class: str, expected: EmissionType
) -> None:
    result = _resolve_plane({"cabin_class": cabin_class})
    assert result == [expected], (
        f"cabin_class={cabin_class!r}: expected [{expected}], got {result}"
    )


@pytest.mark.parametrize(
    "data",
    [
        {"cabin_class": "eco"},  # old wrong frontend value — must NOT match
        {"cabin_class": "premium"},
        {"cabin_class": ""},
        {},  # missing key
    ],
)
def test_resolve_plane_returns_none_for_unknown_class(data: dict) -> None:
    result = _resolve_plane(data)
    assert result is None, (
        f"data={data!r}: expected None for unknown cabin class, got {result}"
    )
