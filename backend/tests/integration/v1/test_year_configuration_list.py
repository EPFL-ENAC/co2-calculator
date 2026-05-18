"""Integration tests for ``GET /api/v1/year-configuration/`` (issue #867 / U2).

The list endpoint feeds the workspace year selector. Backoffice data managers
see every row; everyone else only sees rows where ``is_started`` is true so
closed years stay hidden until backoffice opens them.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from app.models.year_configuration import YearConfiguration

URL = "/api/v1/year-configuration/"


# ---------------------------------------------------------------------------
# Fixtures — minimal scaffolding so the route runs against a real in-memory DB
# but with a fully mocked permission layer (we only care about the is_started
# branch, not the OPA policy chain).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_with_two_years():
    """Spin up an in-memory SQLite, seed two YearConfiguration rows."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        session.add(
            YearConfiguration(
                year=2024,
                is_started=True,
                config={},
                updated_at=datetime.utcnow(),
            )
        )
        session.add(
            YearConfiguration(
                year=2025,
                is_started=False,
                config={},
                updated_at=datetime.utcnow(),
            )
        )
        await session.commit()

        yield session, async_session

    await engine.dispose()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _user() -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.institutional_id = "11111"
    return u


def _wire(monkeypatch, db_factory, *, is_admin: bool) -> None:
    """Inject the seeded session and stub ``is_permitted`` to control the branch."""
    app.dependency_overrides[deps_module.get_current_user] = lambda: _user()

    async def override_get_db():
        async with db_factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db

    async def fake_is_permitted(user, path, action="view"):
        # The endpoint only checks ``backoffice.data_management:view`` — bind
        # the answer to the test parameter.
        if path == "backoffice.data_management" and action == "view":
            return is_admin
        return False

    # Patch the symbol where the route module looked it up at import time.
    monkeypatch.setattr("app.api.v1.year_configuration.is_permitted", fake_is_permitted)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_non_admin_only_sees_started_years(client, monkeypatch, db_with_two_years):
    """Regular users must NOT see the closed (is_started=False) year."""
    _, factory = db_with_two_years
    _wire(monkeypatch, factory, is_admin=False)

    r = client.get(URL)
    assert r.status_code == 200, r.text
    data = r.json()
    assert [row["year"] for row in data] == [2024]
    assert data[0]["is_started"] is True


def test_admin_sees_all_years(client, monkeypatch, db_with_two_years):
    """Backoffice data managers see every row regardless of is_started."""
    _, factory = db_with_two_years
    _wire(monkeypatch, factory, is_admin=True)

    r = client.get(URL)
    assert r.status_code == 200, r.text
    data = r.json()
    # Sorted descending by year.
    assert [row["year"] for row in data] == [2025, 2024]
    assert {row["year"]: row["is_started"] for row in data} == {
        2024: True,
        2025: False,
    }


def test_response_excludes_heavy_config_blob(client, monkeypatch, db_with_two_years):
    """List rows are intentionally lightweight — no ``config`` or
    ``recalculation_status`` payload (callers use ``GET /{year}`` for those)."""
    _, factory = db_with_two_years
    _wire(monkeypatch, factory, is_admin=True)

    r = client.get(URL)
    assert r.status_code == 200, r.text
    row = r.json()[0]
    assert set(row.keys()) == {"year", "is_started", "updated_at"}
