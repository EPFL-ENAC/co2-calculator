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
from app.models.user import UserProvider
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
                provider=UserProvider.DEFAULT,
                is_started=True,
                config={},
                updated_at=datetime.utcnow(),
            )
        )
        session.add(
            YearConfiguration(
                year=2025,
                provider=UserProvider.DEFAULT,
                is_started=False,
                config={},
                updated_at=datetime.utcnow(),
            )
        )
        await session.commit()

        yield session, async_session

    await engine.dispose()


@pytest_asyncio.fixture
async def db_with_two_providers_same_year():
    """Seed YearConfiguration(2026, ACCRED) and YearConfiguration(2026, TEST)
    to verify per-provider isolation: list endpoint must only return the
    row matching ``current_user.provider``.
    """
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
                year=2026,
                provider=UserProvider.ACCRED,
                is_started=True,
                config={"marker": "accred"},
                updated_at=datetime.utcnow(),
            )
        )
        session.add(
            YearConfiguration(
                year=2026,
                provider=UserProvider.TEST,
                is_started=True,
                config={"marker": "test"},
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


def _user(provider: UserProvider = UserProvider.DEFAULT) -> MagicMock:
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.institutional_id = "11111"
    u.provider = provider
    return u


def _wire(
    monkeypatch,
    db_factory,
    *,
    is_admin: bool,
    provider: UserProvider = UserProvider.DEFAULT,
) -> None:
    """Inject the seeded session and stub ``is_permitted`` to control the branch."""
    app.dependency_overrides[deps_module.get_current_user] = lambda: _user(provider)

    async def override_get_db():
        async with db_factory() as session:
            yield session

    app.dependency_overrides[deps_module.get_db] = override_get_db

    async def fake_is_permitted(user, path, action="view"):
        # The list endpoint checks ``backoffice.data_management:view`` (Backoffice
        # Admin readable). The create/update/upload endpoints now check
        # ``system.users:edit`` (Super-Admin-only after #862). Both branches
        # are gated on the same admin flag for this test.
        if path == "backoffice.data_management" and action == "view":
            return is_admin
        if path == "system.users" and action == "edit":
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
    ``recalculation_status`` payload (callers use ``GET /{year}`` for those).

    ``configuration_completed`` (a scalar timestamp added by #1234-followup
    so the dispatch gate can read it without a follow-up call) is in
    scope — it's the lightweight marker, not the heavy blob this test
    guards against.
    """
    _, factory = db_with_two_years
    _wire(monkeypatch, factory, is_admin=True)

    r = client.get(URL)
    assert r.status_code == 200, r.text
    row = r.json()[0]
    assert set(row.keys()) == {
        "year",
        "is_started",
        "configuration_completed",
        "updated_at",
    }


def test_per_provider_isolation_for_same_year(
    client, monkeypatch, db_with_two_providers_same_year
):
    """Two YearConfiguration rows share year=2026 across UserProvider.ACCRED
    and UserProvider.TEST. A TEST user must only see the TEST row, and vice
    versa — the list must NEVER conflate providers.
    """
    _, factory = db_with_two_providers_same_year

    _wire(monkeypatch, factory, is_admin=True, provider=UserProvider.TEST)
    r = client.get(URL)
    assert r.status_code == 200, r.text
    test_rows = r.json()
    assert [row["year"] for row in test_rows] == [2026]

    app.dependency_overrides.clear()

    _wire(monkeypatch, factory, is_admin=True, provider=UserProvider.ACCRED)
    r = client.get(URL)
    assert r.status_code == 200, r.text
    accred_rows = r.json()
    assert [row["year"] for row in accred_rows] == [2026]
    # Different providers, but neither response saw the *other* row;
    # both responses returned exactly one row from a 2-row table.
    assert len(test_rows) == 1 and len(accred_rows) == 1


@pytest_asyncio.fixture
async def db_with_only_accred_2026():
    """Seed a single ACCRED row at year=2026. A TEST user POSTing the same
    year must succeed (201, new TEST row) — the existence check at
    create_year_configuration must be provider-scoped or it would 409.
    """
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
                year=2026,
                provider=UserProvider.ACCRED,
                is_started=True,
                config={"marker": "accred-existing"},
                updated_at=datetime.utcnow(),
            )
        )
        await session.commit()

        yield session, async_session

    await engine.dispose()


def test_post_year_as_test_user_does_not_conflict_with_existing_accred_row(
    client, monkeypatch, db_with_only_accred_2026
):
    """POST /v1/year-configuration/2026 as a TEST user must create the TEST
    row even though an ACCRED row already exists at year=2026. The 409
    existence check must be provider-scoped — otherwise non-ACCRED users
    can never bootstrap their own years once ACCRED has been provisioned.
    """
    _, factory = db_with_only_accred_2026
    _wire(monkeypatch, factory, is_admin=True, provider=UserProvider.TEST)

    # The POST endpoint also enqueues a unit_sync DataIngestionJob and
    # fires ``run_job`` — neither matters for this test's invariant
    # (which is purely the existence-check scoping). Stub fire_and_forget
    # so we don't spawn a coroutine that would crash on the unmocked
    # runner.
    def _consume_coro(coro, *_args, **_kwargs):
        coro.close()
        return None

    monkeypatch.setattr("app.api.v1.year_configuration.fire_and_forget", _consume_coro)

    r = client.post(URL + "2026")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["year"] == 2026
    assert body["is_started"] is False  # default; ACCRED's True must not leak

    # Both rows must coexist — list as ACCRED user should still see the
    # original row, list as TEST user should see the new one.
    app.dependency_overrides.clear()
    _wire(monkeypatch, factory, is_admin=True, provider=UserProvider.ACCRED)
    r = client.get(URL)
    assert r.status_code == 200, r.text
    accred_rows = r.json()
    assert len(accred_rows) == 1
    assert accred_rows[0]["is_started"] is True  # ACCRED untouched
