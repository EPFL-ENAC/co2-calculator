"""Regression tests for ``year`` on the factor lookup endpoints.

These pin two contracts that otherwise regress silently:

- ``GET /v1/factors/{type}/classes/{kind}/values`` **requires** ``year`` — a
  missing year yields 422, never a wrong-year factor. Guards the buildings
  room-defaults fix (``useBuildingRoomDynamicOptions`` now passes year) and
  the equipment power-factor path that already passed it.
- ``GET /v1/factors/{type}/class-subclass-map`` is **scoped to** ``year`` so
  the class/subclass dropdown options match the year-scoped values lookup —
  a class that only has a factor in another year is not offered.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from tests.integration.services.data_ingestion.test_plan_310b_factor_pipeline_pg import (  # noqa: E501
    _make_factor,
)

# DataEntryTypeEnum.scientific — equipment handler, kind_field="equipment_class".
SCIENTIFIC = 10


@pytest_asyncio.fixture
async def pg_app(pg_dsn):
    """Wire the FastAPI app to the test Postgres and bypass auth."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user

    yield {"factory": Sf}

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_values_endpoint_requires_year(pg_app):
    """Missing ``year`` on /values is a 422 — never a silent wrong-year match."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/factors/{SCIENTIFIC}/classes/ClassP/values")

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_class_subclass_map_requires_year(pg_app):
    """Missing ``year`` on class-subclass-map is a 422."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/factors/{SCIENTIFIC}/class-subclass-map")

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_class_subclass_map_scoped_to_year(pg_app):
    """The map returns only classes whose factor matches the queried year."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        session.add_all(
            [
                _make_factor(
                    {"equipment_class": "ClassP", "sub_class": "SubP"},
                    data_entry_type_id=SCIENTIFIC,
                    year=2025,
                ),
                _make_factor(
                    {"equipment_class": "ClassQ", "sub_class": "SubQ"},
                    data_entry_type_id=SCIENTIFIC,
                    year=2024,
                ),
            ]
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            f"/v1/factors/{SCIENTIFIC}/class-subclass-map",
            params={"year": 2025},
        )

    assert resp.status_code == 200, resp.text
    # 2024's ClassQ must NOT leak into the 2025 options.
    assert resp.json() == {"ClassP": ["SubP"]}
