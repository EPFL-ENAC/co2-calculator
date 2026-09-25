"""#2529 — co2.active_users_5m: distinct users per pod, pruned in the callback."""

import pytest

from app.core import active_users


@pytest.fixture
def clock(monkeypatch):
    """A controllable monotonic clock and an empty map, per test."""
    now = [1000.0]
    monkeypatch.setattr(active_users, "monotonic", lambda: now[0])
    monkeypatch.setattr(active_users, "_last_seen", {})
    return now


def _observe() -> list:
    return list(active_users._active_users_callback(None))


def test_counts_distinct_users_and_prunes_past_the_window(clock):
    for user_id in (1, 2, 3, 2):
        active_users.touch(user_id)
    assert [o.value for o in _observe()] == [3]

    clock[0] += active_users.WINDOW_SECONDS + 1
    active_users.touch(2)
    assert [o.value for o in _observe()] == [1]
    assert list(active_users._last_seen) == [2]


def test_observation_carries_no_user_attribute(clock):
    """Cardinality contract: one series per pod, the user id stays in memory."""
    active_users.touch(41)
    (observation,) = _observe()
    assert not observation.attributes


def test_touch_refuses_an_unpersisted_user(clock):
    with pytest.raises(ValueError):
        active_users.touch(None)
