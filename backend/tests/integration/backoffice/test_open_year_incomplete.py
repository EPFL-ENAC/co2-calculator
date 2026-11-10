"""#2787: a year cannot be opened while an enabled module is incomplete.

The ``incomplete`` flag (#1215) was only read by the frontend button; a
stale tab or a direct PATCH still set ``is_started=True``. The API now
answers 409 and names the incomplete modules. Closing stays allowed.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.services.year_config_service import generate_default_year_config
from tests.browser import SAME_ORIGIN_HEADERS
from tests.integration.backoffice.test_incomplete_flag import (
    _seed_jobs_for_full_completion,
)
from tests.integration.backoffice.test_module_activation import URL, YEAR, _wire
from tests.unit.v1.test_temp_upload_auth_ordering import valid_access_token


async def _make_db(*, is_started: bool | None, with_jobs: bool):
    """In-memory DB; ``is_started=None`` leaves the year unconfigured."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        if is_started is not None:
            session.add(
                YearConfiguration(
                    year=YEAR,
                    provider=UserProvider.DEFAULT,
                    is_started=is_started,
                    configuration_completed=datetime.now(UTC),
                    config=generate_default_year_config(),
                )
            )
        if with_jobs:
            session.add_all(_seed_jobs_for_full_completion())
        await session.commit()
    return engine, factory


@pytest_asyncio.fixture
async def closed_incomplete_year():
    engine, factory = await _make_db(is_started=False, with_jobs=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def closed_complete_year():
    engine, factory = await _make_db(is_started=False, with_jobs=True)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def open_incomplete_year():
    engine, factory = await _make_db(is_started=True, with_jobs=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def unconfigured_year():
    engine, factory = await _make_db(is_started=None, with_jobs=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def client():
    with TestClient(
        app,
        cookies={"auth_token": valid_access_token()},
        headers=SAME_ORIGIN_HEADERS,
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_opening_incomplete_year_returns_409(
    client, monkeypatch, closed_incomplete_year
):
    """Regression: the PATCH used to flip ``is_started`` regardless."""
    _wire(monkeypatch, closed_incomplete_year)

    resp = client.patch(URL, json={"is_started": True})

    assert resp.status_code == 409, resp.text
    assert "headcount" in resp.json()["detail"]
    assert client.get(URL).json()["is_started"] is False


def test_opening_complete_year_succeeds(client, monkeypatch, closed_complete_year):
    _wire(monkeypatch, closed_complete_year)

    resp = client.patch(URL, json={"is_started": True})

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_started"] is True


def test_closing_incomplete_year_stays_allowed(
    client, monkeypatch, open_incomplete_year
):
    _wire(monkeypatch, open_incomplete_year)

    resp = client.patch(URL, json={"is_started": False})

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_started"] is False


def test_creating_an_open_incomplete_year_returns_409(
    client, monkeypatch, unconfigured_year
):
    """POST accepts ``is_started`` too, so it gets the same guard."""
    _wire(monkeypatch, unconfigured_year)

    resp = client.post(URL, json={"is_started": True})

    assert resp.status_code == 409, resp.text
    assert "incomplete modules" in resp.json()["detail"]
