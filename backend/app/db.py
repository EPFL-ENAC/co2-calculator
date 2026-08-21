"""Database configuration and session management."""

import json
from collections.abc import AsyncGenerator, Iterable

from opentelemetry.metrics import CallbackOptions, Observation, get_meter
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import Pool, QueuePool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app import models  # noqa: F401 to register models with Base
from app.core.config import Settings, get_settings

settings = get_settings()


def _pool_kwargs(settings: Settings, is_sqlite: bool) -> dict:
    """Explicit QueuePool sizing for ``create_async_engine`` (#1723).

    Skipped for sqlite: its dialect uses ``NullPool``/``StaticPool``,
    neither of which accepts ``pool_size``/``max_overflow``/
    ``pool_timeout`` — passing them raises ``TypeError``.
    """
    if is_sqlite:
        return {}
    return {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
    }


if settings.DB_URL is None:
    raise ValueError("DB_URL must be set")
url = make_url(settings.DB_URL)
is_sqlite = False
if (
    url.drivername == "sqlite" or url.drivername == "sqlite3"
) and not url.drivername.endswith("+aiosqlite"):
    # Add async driver for SQLite
    url = url.set(drivername="sqlite+aiosqlite")
    is_sqlite = True

if (
    url.drivername == "postgresql"
    or url.drivername == "postgres"
    or url.drivername == "postgresql+psycopg"
) and not url.drivername.endswith("+asyncpg"):
    # Preserve existing query params and add async_fallback
    existing_query = dict(url.query)
    existing_query["async_fallback"] = "true"
    url = url.set(drivername="postgresql+psycopg", query=existing_query)

# Use the modified url for the engine
final_db_url = url.render_as_string(hide_password=False)

engine = create_async_engine(
    final_db_url,  # This has the actual password
    pool_pre_ping=True,  # Verify connections before using them
    # echo=settings.DEBUG,  # Log SQL queries in debug mode
    connect_args={"check_same_thread": False} if is_sqlite else {},
    json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    **_pool_kwargs(settings, is_sqlite),
)


def read_pool_state(pool: Pool) -> dict[str, int] | None:
    """Snapshot a SQLAlchemy pool's live connection counts.

    ``QueuePool`` (Postgres, production) implements ``checkedout()``/
    ``size()``/``overflow()``; ``NullPool``/``StaticPool`` (sqlite, tests)
    don't -- there's no pool to observe there, so this returns ``None``
    rather than raising.
    """
    if not isinstance(pool, QueuePool):
        return None
    return {
        "checked_out": pool.checkedout(),
        "size": pool.size(),
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
