"""Unit tests for #1723 explicit async-engine pool sizing.

``app.db._pool_kwargs`` builds the ``pool_size``/``max_overflow``/
``pool_timeout`` kwargs passed to ``create_async_engine`` — extracted
into its own function specifically so this settings-passthrough can be
asserted without importing the whole ``app.db`` module (which builds a
real engine at import time from whatever ``DB_URL`` is in the test
environment) or mocking ``create_async_engine`` through a module reload.
"""

from app.core.config import Settings
from app.db import _pool_kwargs


def test_pool_kwargs_passes_settings_through_for_postgres():
    """DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT reach the kwargs
    dict spread into create_async_engine(**_pool_kwargs(...)) verbatim."""
    settings = Settings(DB_POOL_SIZE=7, DB_MAX_OVERFLOW=3, DB_POOL_TIMEOUT=9)

    kwargs = _pool_kwargs(settings, is_sqlite=False)

    assert kwargs == {
        "pool_size": 7,
        "max_overflow": 3,
        "pool_timeout": 9,
    }


def test_pool_kwargs_empty_for_sqlite():
    """SQLite uses NullPool/StaticPool, which reject pool_size /
    max_overflow / pool_timeout — they must NOT be passed."""
    settings = Settings(DB_POOL_SIZE=7, DB_MAX_OVERFLOW=3, DB_POOL_TIMEOUT=9)

    assert _pool_kwargs(settings, is_sqlite=True) == {}


def test_pool_settings_defaults_match_plan():
    """Pin the shipped defaults (10/10/30) — doubled pool_size vs the
    SQLAlchemy default (5) that produced the original QueuePool
    exhaustion error, per docs/src/implementation-plans/
    1723-job-concurrency-and-db-pool.md."""
    assert Settings.model_fields["DB_POOL_SIZE"].default == 10
    assert Settings.model_fields["DB_MAX_OVERFLOW"].default == 10
    assert Settings.model_fields["DB_POOL_TIMEOUT"].default == 30


def test_max_concurrent_jobs_default_matches_plan():
    """Pin the shipped default (4/pod) — see the "Implementation notes"
    section of the #1723 plan for why 4 was kept over the plan's 8
    alternate."""
    assert Settings.model_fields["MAX_CONCURRENT_JOBS"].default == 4
