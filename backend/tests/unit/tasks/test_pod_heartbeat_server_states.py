"""#2854 — this pod's server-side connections by state, from the heartbeat."""

import pytest

from app.tasks import _pod_heartbeat as hb


@pytest.mark.parametrize(
    "raw,folded",
    [
        ("idle", "idle"),
        (None, "idle"),
        ("active", "active"),
        ("idle in transaction", "idle in transaction"),
        ("idle in transaction (aborted)", "idle in transaction"),
        ("fastpath function call", "active"),
        ("disabled", "active"),
    ],
)
def test_fold_server_state_maps_every_postgres_state_onto_three(raw, folded):
    assert hb.fold_server_state(raw) == folded


def test_by_state_gauge_is_silent_before_the_first_tick():
    """Same contract as db.server.connections: no zeros that look measured."""
    hb._pod_server_states = None
    assert list(hb._pod_server_states_callback(None)) == []


def test_by_state_gauge_emits_all_three_states_with_zeros():
    """A stacked panel needs a continuous series per state, so an absent
    state is reported as 0 once the first tick has run.
    """
    hb._pod_server_states = {"idle": 4, "active": 1, "idle in transaction": 0}
    observed = {
        o.attributes["state"]: o.value for o in hb._pod_server_states_callback(None)
    }
    assert observed == {"idle": 4, "active": 1, "idle in transaction": 0}
    hb._pod_server_states = None


def test_by_state_sql_is_scoped_to_this_pod_and_client_backends():
    """Each pod reports only itself: application_name is co2-<POD_ID> (#2689),
    and background workers must not count, same as SERVER_CONNECTIONS_SQL.
    """
    assert "application_name = :app" in hb.POD_SERVER_STATES_SQL
    assert "backend_type = 'client backend'" in hb.POD_SERVER_STATES_SQL
    assert "GROUP BY state" in hb.POD_SERVER_STATES_SQL
