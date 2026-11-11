"""Unit tree levels come from the configuration (#500)."""

import pytest

from app.core.config import get_settings
from app.core.unit_levels import affiliation_levels, workspace_level


def test_levels_follow_the_settings(monkeypatch):
    monkeypatch.setattr(get_settings(), "UNIT_WORKSPACE_LEVEL", 3)
    monkeypatch.setattr(get_settings(), "UNIT_AFFILIATION_LEVELS", " 1, 2 ")

    assert workspace_level() == 3
    assert affiliation_levels() == [1, 2]


def test_missing_workspace_level_stops_the_startup(monkeypatch):
    monkeypatch.setattr(get_settings(), "UNIT_WORKSPACE_LEVEL", None)

    with pytest.raises(ValueError, match="UNIT_WORKSPACE_LEVEL"):
        workspace_level()


@pytest.mark.parametrize("value", ["", "2,three"])
def test_missing_or_wrong_affiliation_levels_stop_the_startup(monkeypatch, value):
    monkeypatch.setattr(get_settings(), "UNIT_AFFILIATION_LEVELS", value)

    with pytest.raises(ValueError, match="UNIT_AFFILIATION_LEVELS"):
        affiliation_levels()
