"""Unit tests for #1723 explicit async-engine pool sizing.

``app.db._pool_kwargs`` builds the ``pool_size``/``max_overflow``/
``pool_timeout`` kwargs passed to ``create_async_engine`` — extracted
into its own function specifically so this settings-passthrough can be
asserted without importing the whole ``app.db`` module (which builds a
real engine at import time from whatever ``DB_URL`` is in the test
environment) or mocking ``create_async_engine`` through a module reload.
"""

from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.util import greenlet_spawn

from app import db
from app.core.config import Settings
from app.db import (
    InstrumentedQueuePool,
    _connect_args,
    _normalize_url,
    _pool_kwargs,
    connect_failure_sqlstate,
    count_connect_failure,
    read_pool_state,
)


def test_pool_kwargs_passes_settings_through_for_postgres():
    """DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT reach the kwargs
    dict spread into create_async_engine(**_pool_kwargs(...)) verbatim.

    ``poolclass`` joined them in #2572: the checkout-timeout counter lives
    on the pool class, so this is also what keeps it out of sqlite's way.
    """
    settings = Settings(DB_POOL_SIZE=7, DB_MAX_OVERFLOW=3, DB_POOL_TIMEOUT=9)

    kwargs = _pool_kwargs(settings, is_sqlite=False)

    assert kwargs == {
        "poolclass": InstrumentedQueuePool,
        "pool_size": 7,
        "max_overflow": 3,
        "pool_timeout": 9,
    }


def test_pool_kwargs_empty_for_sqlite():
    """SQLite uses NullPool/StaticPool, which reject pool_size /
    max_overflow / pool_timeout — they must NOT be passed.
    """
    settings = Settings(DB_POOL_SIZE=7, DB_MAX_OVERFLOW=3, DB_POOL_TIMEOUT=9)

    assert _pool_kwargs(settings, is_sqlite=True) == {}


def test_pool_settings_defaults_match_plan():
    """Pin the shipped defaults (10/10/5) — doubled pool_size vs the
    SQLAlchemy default (5) that produced the original QueuePool
    exhaustion error, per docs/src/implementation-plans/
    1723-job-concurrency-and-db-pool.md.

    ``DB_POOL_TIMEOUT`` dropped 30 → 5 in #2572: a checkout that waits
    that long has already failed the request, so 30s only buys the user a
    longer spinner before the same error, and delays the signal.
    """
    assert Settings.model_fields["DB_POOL_SIZE"].default == 10
    assert Settings.model_fields["DB_MAX_OVERFLOW"].default == 10
    assert Settings.model_fields["DB_POOL_TIMEOUT"].default == 5


def test_max_concurrent_jobs_default_matches_plan():
    """Pin the shipped default (4/pod) — see the "Implementation notes"
    section of the #1723 plan for why 4 was kept over the plan's 8
    alternate.
    """
    assert Settings.model_fields["MAX_CONCURRENT_JOBS"].default == 4


def test_read_pool_state_reads_queuepool_live_counts():
    """#2050 Track I1a: the OTel gauge callback's data source. QueuePool
    is the only pool type in production (Postgres) -- checked_out/size/
    overflow must come back as the pool's real, live numbers.

    ``checked_in`` joined them in #2566: ``checked_in + checked_out`` is
    the count that fills the server's ``max_connections``, and it was the
    series missing from the dashboard during that incident.

    So did ``max_overflow``, which reads SQLAlchemy's private
    ``_max_overflow``: this assertion is what makes a rename upstream fail
    here instead of silently moving a dashboard's denominator. Note
    ``overflow`` is NOT that limit -- it starts at ``-pool_size`` and
    counts connections created beyond ``size``.
    """
    pool = QueuePool(creator=lambda: None, pool_size=15, max_overflow=5)

    state = read_pool_state(pool)

    assert state == {
        "checked_out": 0,
        "checked_in": 0,
        "size": 15,
        "max_overflow": 5,
        "overflow": -15,
    }


def test_read_pool_state_none_for_non_queuepool():
    """Sqlite's NullPool has no checkedout()/size()/overflow() -- must
    return None, not raise, so the gauge callback can just skip it.
    """
    pool = NullPool(creator=lambda: None)

    assert read_pool_state(pool) is None


def test_postgres_connect_args_enable_tcp_keepalives():
    """#2566: psycopg leaves keepalives off, so a pod whose server vanished
    mid-connection waits out the OS default (~2h) instead of failing. These
    four settings cap that at roughly 60s: idle 30s, then 3 probes 10s apart.
    """
    assert _connect_args(is_sqlite=False) == {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }


def test_sqlite_connect_args_carry_no_libpq_options():
    """Aiosqlite raises ``TypeError: Connection() got an unexpected keyword
    argument 'keepalives'`` on anything from the Postgres set.
    """
    assert _connect_args(is_sqlite=True) == {"check_same_thread": False}


def test_already_async_sqlite_url_is_detected_as_sqlite():
    """Regression, #2566: the check was ``drivername == "sqlite"``, so the
    shipped default -- which already names the async driver -- fell through
    to the Postgres branch. It only ever looked harmless because the
    Postgres connect args were empty at the time.
    """
    url, is_sqlite = _normalize_url("sqlite+aiosqlite:///./co2_calculator.db")

    assert is_sqlite is True
    assert url.drivername == "sqlite+aiosqlite"


def test_bare_sqlite_url_gains_the_async_driver():
    url, is_sqlite = _normalize_url("sqlite:///./co2_calculator.db")

    assert is_sqlite is True
    assert url.drivername == "sqlite+aiosqlite"


def test_postgres_url_gains_psycopg_and_async_fallback():
    url, is_sqlite = _normalize_url("postgresql://user:pw@db.example.org/app")

    assert is_sqlite is False
    assert url.drivername == "postgresql+psycopg"
    assert url.query["async_fallback"] == "true"


def test_shipped_default_db_url_is_sqlite():
    """Ties the detection to the actual default rather than a literal in
    this test -- CI runs with no .env, so this is the URL it uses.
    """
    default = Settings.model_fields["DB_URL"].default

    assert _normalize_url(default)[1] is True


class _RecordingCounter:
    """Stands in for the OTel counter and keeps what would be exported."""

    def __init__(self):
        self.calls: list[tuple[int, dict | None]] = []

    def add(self, amount, attributes=None):
        self.calls.append((amount, attributes))


class _FakeDBAPIConnection:
    """The only two methods QueuePool calls on a pooled connection."""

    def rollback(self):
        pass

    def close(self):
        pass


async def test_pool_checkout_timeout_increments_the_counter(monkeypatch):
    """#2572: a real checkout timeout, not a mocked one — the whole point
    of the issue is that the obvious hook (``handle_error``) never sees
    this exception, so only an actual exhausted pool proves the counter.

    ``greenlet_spawn`` is what the async engine wraps every pool call in;
    without it ``AsyncAdaptedQueuePool``'s wait raises ``MissingGreenlet``.
    """
    counter = _RecordingCounter()
    monkeypatch.setattr(db, "_pool_timeouts", counter)
    pool = InstrumentedQueuePool(
        creator=_FakeDBAPIConnection, pool_size=1, max_overflow=0, timeout=0.1
    )
    held = await greenlet_spawn(pool.connect)

    with pytest.raises(SQLAlchemyTimeoutError):
        await greenlet_spawn(pool.connect)

    assert counter.calls == [(1, None)]
    held.close()


async def test_successful_checkout_does_not_increment_the_counter(monkeypatch):
    """A counter that ticks on healthy traffic makes ``increase(...) > 0``
    alerting useless.
    """
    counter = _RecordingCounter()
    monkeypatch.setattr(db, "_pool_timeouts", counter)
    pool = InstrumentedQueuePool(
        creator=_FakeDBAPIConnection, pool_size=1, max_overflow=0, timeout=0.1
    )

    connection = await greenlet_spawn(pool.connect)
    connection.close()

    assert counter.calls == []


@pytest.mark.parametrize(
    "message",
    [
        "FATAL:  sorry, too many clients already",
        "FATAL:  remaining connection slots are reserved for roles with the "
        "SUPERUSER attribute",
        'FATAL:  too many connections for role "app"',
        'FATAL:  too many connections for database "app"',
    ],
)
def test_too_many_connections_is_labelled_53300(message):
    """The outage mode of #2566. Postgres has four ways of saying it, and
    psycopg drops the SQLSTATE on connect errors — verified against a real
    53300 forced by a role CONNECTION LIMIT — so the text is all there is.
    """
    error = psycopg.OperationalError(f"connection failed: {message}")

    assert connect_failure_sqlstate(error) == "53300"


def test_unrecognised_connect_failure_is_labelled_unknown():
    """Still counted, never dropped: the total is what says "connections
    are failing", the label only says which kind.
    """
    error = psycopg.OperationalError(
        'connection to server at "127.0.0.1", port 5432 failed: Connection refused'
    )

    assert connect_failure_sqlstate(error) == "unknown"


def test_a_real_sqlstate_wins_over_the_message():
    """Message matching only exists because psycopg has no SQLSTATE to
    give at connect time; where one exists it is the answer.
    """
    error = psycopg.errors.TooManyConnections("too many clients already")

    assert connect_failure_sqlstate(error) == "53300"


def test_connect_failure_counted_with_its_sqlstate_label(monkeypatch):
    """``handle_error`` fires with no connection when the failure happened
    before one existed — that is the connect path.
    """
    counter = _RecordingCounter()
    context = SimpleNamespace(
        connection=None,
        original_exception=psycopg.OperationalError(
            "connection failed: FATAL:  sorry, too many clients already"
        ),
    )

    monkeypatch.setattr(db, "_connect_failures", counter)

    count_connect_failure(context)

    assert counter.calls == [(1, {"sqlstate": "53300"})]


def test_query_errors_are_not_counted_as_connect_failures(monkeypatch):
    """``handle_error`` fires for every DBAPI error. One raised on an open
    connection is a query failing, not the server refusing connections.
    """
    counter = _RecordingCounter()
    context = SimpleNamespace(
        connection=object(),
        original_exception=psycopg.errors.DivisionByZero("division by zero"),
    )

    monkeypatch.setattr(db, "_connect_failures", counter)

    count_connect_failure(context)

    assert counter.calls == []
