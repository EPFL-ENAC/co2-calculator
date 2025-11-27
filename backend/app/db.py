"""Database configuration and session management."""

from typing import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlmodel import SQLModel

from app import models  # noqa: F401 to register models with Base
from app.core.config import get_settings

settings = get_settings()

url = make_url(settings.db_url)
is_sqlite = False
if (
    url.drivername == "sqlite" or url.drivername == "sqlite3"
) and not url.drivername.endswith("+aiosqlite"):
    # Add async driver for SQLite
    async_url = url.set(drivername="sqlite+aiosqlite")
    settings.db_url = str(async_url)
    is_sqlite = True
# Create SQLAlchemy engine

if (
    url.drivername == "postgresql"
    or url.drivername == "postgres"
    or url.drivername == "postgresql+psycopg"
) and not url.drivername.endswith("+asyncpg"):
    # Add async driver + optional query params
    async_url = url.set(
        drivername="postgresql+psycopg", query={"async_fallback": "true"}
    )
    settings.DB_URL = str(async_url)

engine = create_async_engine(
    settings.db_url,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

# Create SessionLocal class
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create Base class for declarative models
Base = declarative_base()


async def get_db_session() -> AsyncSession:
    """
    Utility to get a single AsyncSession (not as a dependency).
    Use for internal checks like health endpoints.
    """
    return SessionLocal()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

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
