"""Database configuration and session management."""

import json
import logging
from collections.abc import AsyncGenerator, Iterable

from opentelemetry.metrics import CallbackOptions, Observation, get_meter
from sqlalchemy import event
from sqlalchemy.engine import ExceptionContext
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import (
    AsyncAdaptedQueuePool,
    Pool,
    PoolProxiedConnection,
    QueuePool,
)
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app import models  # noqa: F401 to register models with Base
from app.core.config import Settings, get_settings

settings = get_settings()

# #2572: both DB failure modes were only ever inferred from gauge
# thresholds, so a burst that started and recovered inside the alert window
# never fired. Counters make ``increase(...) > 0`` possible instead.
_pool_timeouts = get_meter(__name__).create_counter(
    "db.pool.timeouts",
    unit="{timeout}",
    description=(
        "Pool checkouts that gave up waiting for a free connection -- the "
        "pod-local, recoverable failure mode."
    ),
)

_connect_failures = get_meter(__name__).create_counter(
    "db.connect.failures",
    unit="{failure}",
    description=(
        "Failed attempts to establish a DB connection, by SQLSTATE. 53300 "
        "(too_many_connections) is the server-wide outage mode."
    ),
)

# Postgres answers "the server is full" (SQLSTATE 53300) with four
# different messages, depending on which limit was reached.
_TOO_MANY_CONNECTIONS_MESSAGES = (
    "too many clients already",
    "remaining connection slots are reserved",
    "too many connections for role",
    "too many connections for database",
)


class InstrumentedQueuePool(AsyncAdaptedQueuePool):
    """Count pool checkout timeouts (#2572).

    ``handle_error`` is the obvious hook and does not work: a checkout
    timeout never reaches the DBAPI, so no listener on that event ever
    sees one. ``Pool.connect()`` is the single call every checkout makes,
    so it counts exactly one timeout per timed-out request -- unlike
    ``_do_get``, which re-enters itself on the overflow path.
    """

    def connect(self) -> PoolProxiedConnection:
        try:
            return super().connect()
        except SQLAlchemyTimeoutError:
            _pool_timeouts.add(1)
            raise


# SQLAlchemy names a pool's logger after the pool class's module, so the
# #2572 subclass silently moved it from ``sqlalchemy.pool.impl.*`` (outside
# the app logging config, never seen) to ``app.db.*`` -- and dev runs
# LOG_LEVEL=DEBUG, which turned every checkout into six log lines. Pin the
# logger at INFO: warnings still flow, the per-checkout diary does not.
logging.getLogger(f"{__name__}.{InstrumentedQueuePool.__name__}").setLevel(logging.INFO)


def connect_failure_sqlstate(error: BaseException) -> str:
    """Label a failed connection attempt for ``db.connect.failures``.

    psycopg drops the SQLSTATE on connection-*establishment* errors: the
    server's ErrorResponse survives only as message text, so the outage
    mode has to be recognised from that. Unrecognised failures are still
    counted, as ``unknown``, rather than dropped.
    """
    sqlstate = getattr(error, "sqlstate", None)
    if sqlstate is not None:
        return str(sqlstate)
    message = str(error)
    if any(marker in message for marker in _TOO_MANY_CONNECTIONS_MESSAGES):
        return "53300"
    return "unknown"


def count_connect_failure(context: ExceptionContext) -> None:
    """``handle_error`` fires for every DBAPI error, so narrow it twice.

    An error carrying a connection is a query failing, not a connection
    refused. A failed ``pool_pre_ping`` is the pool healing itself: since
    #2566 the server reaps idle backends after 30 min, so every such
    checkout raises here and then reconnects and succeeds. Counting those
    would tick this counter all day on a healthy pod. When the reconnect
    *also* fails, that attempt fires its own event with ``is_pre_ping``
    false -- which is the one worth counting.
    """
    if context.connection is not None or context.is_pre_ping:
        return
    label = connect_failure_sqlstate(context.original_exception)
    _connect_failures.add(1, {"sqlstate": label})


def _pool_kwargs(settings: Settings, is_sqlite: bool) -> dict:
    """Explicit QueuePool sizing and class for ``create_async_engine``.

    Skipped for sqlite: its dialect uses ``NullPool``/``StaticPool``,
    neither of which accepts ``pool_size``/``max_overflow``/
    ``pool_timeout`` — passing them raises ``TypeError`` (#1723). That
    same guard is what keeps the timeout counter a no-op there (#2572).
    """
    if is_sqlite:
        return {}
    return {
        "poolclass": InstrumentedQueuePool,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
    }


def _normalize_url(raw: str) -> tuple[URL, bool]:
    """Pick the async driver for ``DB_URL``, and report which backend it is.

    Extracted for the same reason as ``_pool_kwargs``: the sqlite flag
    selects both the pool kwargs and the connect args, and it has to be
    assertable without building a real engine from the ambient environment.
    """
    url = make_url(raw)
    # Backend name, not drivername: the default DB_URL is already
    # "sqlite+aiosqlite://", which the old ``== "sqlite"`` test missed -- so
    # sqlite silently took the Postgres branch and got handed libpq's
    # connect args (#2566).
    is_sqlite = url.get_backend_name() == "sqlite"
    if is_sqlite and not url.drivername.endswith("+aiosqlite"):
        # Add async driver for SQLite
        url = url.set(drivername="sqlite+aiosqlite")

    if (
        url.drivername == "postgresql"
        or url.drivername == "postgres"
        or url.drivername == "postgresql+psycopg"
    ) and not url.drivername.endswith("+asyncpg"):
        # Preserve existing query params and add async_fallback
        existing_query = dict(url.query)
        existing_query["async_fallback"] = "true"
        url = url.set(drivername="postgresql+psycopg", query=existing_query)
    return url, is_sqlite


if settings.DB_URL is None:
    raise ValueError("DB_URL must be set")
url, is_sqlite = _normalize_url(settings.DB_URL)

# Use the modified url for the engine
final_db_url = url.render_as_string(hide_password=False)

# #2566: without these a pod cannot tell a dead server from an idle one.
# When the cluster restarted the network under stage's established
# connections, every pooled socket became a black hole and probes timed out
# instead of failing -- the OS default is ~2h before the kernel gives up.
# Probing every 30s means a pod notices in ~60s and reconnects. This is the
# client half only; the server reaps its own orphans via the role's
# tcp_keepalives_* (applied on the DB, not here).
_PG_KEEPALIVES = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}


def _connect_args(is_sqlite: bool) -> dict:
    """Driver-specific connect kwargs. Extracted for the same reason as
    ``_pool_kwargs``: assertable without building a real engine.

    These are not interchangeable -- aiosqlite raises ``TypeError:
    Connection() got an unexpected keyword argument 'keepalives'`` on the
    Postgres set, and sqlite3's ``check_same_thread`` is meaningless to
    libpq.
    """
    if is_sqlite:
        return {"check_same_thread": False}
    return dict(_PG_KEEPALIVES)


engine = create_async_engine(
    final_db_url,  # This has the actual password
    pool_pre_ping=True,  # Verify connections before using them
    # echo=settings.DEBUG,  # Log SQL queries in debug mode
    connect_args=_connect_args(is_sqlite),
    json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    **_pool_kwargs(settings, is_sqlite),
)

# Sqlite has no server to run out of connections, and no SQLSTATE to label
# a failure with -- mirror the sqlite guard the pool kwargs already use.
if not is_sqlite:
    event.listen(engine.sync_engine, "handle_error", count_connect_failure)


def read_pool_state(pool: Pool) -> dict[str, int] | None:
    """Snapshot a SQLAlchemy pool's live connection counts.

    ``QueuePool`` (Postgres, production) implements ``checkedout()``/
    ``size()``/``overflow()``; ``NullPool``/``StaticPool`` (sqlite, tests)
    don't -- there's no pool to observe there, so this returns ``None``
    rather than raising.

    ``checked_in`` is what makes the numbers comparable to
    ``max_connections`` (#2566): ``checked_out`` alone reads as healthy
    (13 fleet-wide) while ``checked_in + checked_out`` -- the sockets
    actually open against Postgres -- is what fills the server.

    ``max_overflow`` completes the pod's real ceiling, ``size +
    max_overflow``. Without it the saturation panel and its alert have to
    hardcode DB_MAX_OVERFLOW, which lives in a different repo
    (openshift-app-config) -- and a change on either side would silently
    move the denominator. ``overflow()`` is not that number: it is
    ``_overflow``, a *count* of connections created beyond ``size``,
    initialised to ``-pool_size``.

    ``_max_overflow`` is private API. The test below pins it against a
    hand-built QueuePool, so a rename upstream fails loudly here rather
    than quietly wrong in a dashboard.
    """
    if not isinstance(pool, QueuePool):
        return None
    return {
        "checked_out": pool.checkedout(),
        "checked_in": pool.checkedin(),
        "size": pool.size(),
        "max_overflow": pool._max_overflow,
        "overflow": pool.overflow(),
    }


def _pool_metrics_callback(options: CallbackOptions) -> Iterable[Observation]:
    """#2050 Track I1a: report this pod's connection-pool state.

    A1/A4/H8 all independently pointed at pod-local pool exhaustion as a
    request-latency mechanism ("connect span" cost, /ready pool waits),
    diagnosed each time by a one-off kubectl exec + hand-written query.
    This turns that into a standing metric instead.
    """
    state = read_pool_state(engine.pool)
    if state is None:
        return
    for label, value in state.items():
        yield Observation(value, {"state": label})


get_meter(__name__).create_observable_gauge(
    "db.pool.connections",
    callbacks=[_pool_metrics_callback],
    unit="{connection}",
    description="SQLAlchemy connection pool state for this pod",
)

# Create SessionLocal class
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create Base class for declarative models
Base = declarative_base()


async def get_db_session() -> AsyncSession:
    """Utility to get a single AsyncSession (not as a dependency).
    Use for internal checks like health endpoints.
    """
    return SessionLocal()


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependency to get database session.

    Yields:
        Database session

    Example:
        @app.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with SessionLocal() as db:
        yield db


async def init_db() -> None:
    """Initialize database tables."""
    # Import all models here to ensure they are registered with Base
    print("Initializing database tables...")
    # SQLModel.metadata.create_all(engine)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
