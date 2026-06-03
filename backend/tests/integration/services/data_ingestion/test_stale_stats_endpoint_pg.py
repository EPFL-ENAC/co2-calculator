"""Integration tests for ``GET /v1/sync/health/stale-stats`` against a
real Postgres.

Plan 310-D Follow-up 1 (#1063) — read-only backstop endpoint that walks
``carbon_report_modules`` × ``carbon_reports.year`` (the source-of-truth
for "what should have an aggregation") and returns one entry per
``(module_type_id, year)`` whose latest ``job_type='aggregation'`` row
is missing, failed, stuck, or too old.

Each ``why_stale`` bucket gets its own dedicated scope here: a single
seed exercising all four classifications side-by-side proves the
endpoint is bucketing rows correctly and stamping ``last_aggregation_job_id``
from the right row.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
)
from app.models.unit import Unit
from app.models.user import UserProvider

# Four module_type_ids — one per why_stale bucket — keep classifications
# decoupled from each other.  Concrete ModuleTypeEnum values aren't
# required (the seed query keys on module_type_id integers), but using
# real ints keeps the test honest about the production schema.
_MT_NO_AGG = 1  # ModuleTypeEnum.headcount
_MT_FAILED = 2  # ModuleTypeEnum.professional_travel
_MT_TOO_OLD = 3  # ModuleTypeEnum.buildings
_MT_STUCK = 4  # ModuleTypeEnum.equipment_electric_consumption

_YEAR = 2025


def _make_aggregation(
    *,
    module_type_id: int,
    year: int,
    state: IngestionState,
    result: IngestionResult | None = None,
    finished_at: datetime | None = None,
) -> DataIngestionJob:
    """Construct a ``job_type='aggregation'`` row for seeding.

    Mirrors the shape ``_chain.py`` produces — entity_type per-year,
    ingestion_method=computed (aggregation isn't a CSV/API ingest, it's
    derived) — so tests stay close to production rows.
    """
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        year=year,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=state,
        result=result,
        finished_at=finished_at,
        job_type="aggregation",
        is_current=False,
        meta={},
    )


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    Same pattern as ``test_factors_stale_endpoint_pg.py``: use the
    ``pg_dsn`` fixture so the production schema's partial unique
    indexes (and any future per-batch DDL added there) are present even
    though our seed doesn't actually need them.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)

    yield {"factory": Sf, "engine": engine}

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_four_buckets(Sf) -> dict[str, int | None]:
    """Seed one scope per ``why_stale`` bucket and one fresh-success
    control scope (which must NOT surface).

    Returns a dict mapping bucket key → expected ``last_aggregation_job_id``
    (None for the no-aggregation-ever scope).
    """
    now = datetime.now(timezone.utc)
    expected: dict[str, int | None] = {}

    async with Sf() as s:
        unit = Unit(
            institutional_code="STALE-TEST",
            institutional_id="STALE-TEST-UNIT",
            name="Stale Stats Test Unit",
            level=1,
        )
        s.add(unit)
        await s.commit()
        assert unit.id is not None
        unit_id: int = unit.id

        report = CarbonReport(year=_YEAR, unit_id=unit_id)
        s.add(report)
        await s.commit()
        assert report.id is not None
        report_id: int = report.id

        # ── Seed one CarbonReportModule per bucket ─────────────────────
        # The endpoint's seed-of-truth is carbon_report_modules; without
        # these rows the LEFT JOIN drops the scopes entirely.
        for mt in (_MT_NO_AGG, _MT_FAILED, _MT_TOO_OLD, _MT_STUCK):
            s.add(
                CarbonReportModule(
                    carbon_report_id=report_id,
                    module_type_id=mt,
                )
            )
        # Also seed a fresh-success control scope — must NOT show up in
        # the response.
        _MT_FRESH = 5  # ModuleTypeEnum.purchase
        s.add(
            CarbonReportModule(
                carbon_report_id=report_id,
                module_type_id=_MT_FRESH,
            )
        )
        await s.commit()

        # ── Seed aggregation jobs for buckets that have one ────────────
        # last_aggregation_failed
        failed_job = _make_aggregation(
            module_type_id=_MT_FAILED,
            year=_YEAR,
            state=IngestionState.FINISHED,
            result=IngestionResult.ERROR,
            finished_at=now - timedelta(minutes=5),
        )
        s.add(failed_job)

        # last_aggregation_too_old — finished_at well outside any
        # reasonable threshold.
        too_old_job = _make_aggregation(
            module_type_id=_MT_TOO_OLD,
            year=_YEAR,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            finished_at=now - timedelta(days=2),
        )
        s.add(too_old_job)

        # pending_aggregation_stuck — NOT_STARTED, never picked up.
        stuck_job = _make_aggregation(
            module_type_id=_MT_STUCK,
            year=_YEAR,
            state=IngestionState.NOT_STARTED,
        )
        s.add(stuck_job)

        # Fresh control — FINISHED + SUCCESS + recent.  Must be excluded.
        fresh_job = _make_aggregation(
            module_type_id=_MT_FRESH,
            year=_YEAR,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            finished_at=now,
        )
        s.add(fresh_job)

        await s.commit()
        expected["last_aggregation_failed"] = failed_job.id
        expected["last_aggregation_too_old"] = too_old_job.id
        expected["pending_aggregation_stuck"] = stuck_job.id
        expected["no_aggregation_ever"] = None

    return expected


@pytest.mark.asyncio
async def test_stale_stats_classifies_each_why_stale_bucket(pg_app):
    """End-to-end: seed all four ``why_stale`` shapes plus a fresh
    control, hit the endpoint, assert each entry has the correct
    classification + the correct ``last_aggregation_job_id``."""
    Sf = pg_app["factory"]
    expected = await _seed_four_buckets(Sf)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Threshold = 60 min — well below the 2-day too-old job's age and
        # well above the 5-min failed job's age.  finished_at is
        # irrelevant for the failed/stuck buckets, but exercising a
        # realistic value keeps the test honest.
        resp = await client.get(
            "/v1/sync/health/stale-stats", params={"older_than_minutes": 60}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    # Four stale buckets, fresh control excluded.
    assert len(body) == 4, f"Expected 4 stale rows, got {body!r}"

    by_module = {row["module_type_id"]: row for row in body}
    assert set(by_module.keys()) == {_MT_NO_AGG, _MT_FAILED, _MT_TOO_OLD, _MT_STUCK}

    no_agg = by_module[_MT_NO_AGG]
    assert no_agg["why_stale"] == "no_aggregation_ever"
    assert no_agg["last_aggregation_job_id"] is None
    assert no_agg["last_finished_aggregation_at"] is None
    assert no_agg["year"] == _YEAR

    failed = by_module[_MT_FAILED]
    assert failed["why_stale"] == "last_aggregation_failed"
    assert failed["last_aggregation_job_id"] == expected["last_aggregation_failed"]
    assert failed["last_finished_aggregation_at"] is not None
    assert failed["year"] == _YEAR

    too_old = by_module[_MT_TOO_OLD]
    assert too_old["why_stale"] == "last_aggregation_too_old"
    assert too_old["last_aggregation_job_id"] == expected["last_aggregation_too_old"]
    assert too_old["last_finished_aggregation_at"] is not None
    assert too_old["year"] == _YEAR

    stuck = by_module[_MT_STUCK]
    assert stuck["why_stale"] == "pending_aggregation_stuck"
    assert stuck["last_aggregation_job_id"] == expected["pending_aggregation_stuck"]
    # NOT_STARTED rows haven't finished — no finished_at to surface.
    assert stuck["last_finished_aggregation_at"] is None
    assert stuck["year"] == _YEAR


@pytest.mark.asyncio
async def test_stale_stats_returns_403_for_user_without_permission(pg_dsn, monkeypatch):
    """Permission gate — ``GET /v1/sync/health/stale-stats`` is behind
    ``backoffice.data_management.view``.  Users without that permission
    get HTTP 403, not the stale list.

    Bypasses ``pg_app`` (which monkeypatches ``is_permitted`` to True) so
    the real permission check fires.  Mirrors the pattern in
    ``test_factors_stale_endpoint_pg.py``."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.core.security.is_permitted", _deny)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/v1/sync/health/stale-stats")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_stale_stats_returns_empty_list_with_no_modules(pg_app):
    """No ``carbon_report_modules`` rows → endpoint returns ``[]``.

    The endpoint's seed is the modules table; if no module declares a
    scope, there's nothing to be stale about — even if orphan aggregation
    rows exist for unrelated module types.  Validates that the LEFT JOIN
    starts from modules and not from jobs."""
    Sf = pg_app["factory"]

    # Seed a stuck aggregation row WITHOUT a matching CarbonReportModule.
    # If the query joined the wrong direction it would surface here.
    async with Sf() as s:
        s.add(
            _make_aggregation(
                module_type_id=99,
                year=_YEAR,
                state=IngestionState.NOT_STARTED,
            )
        )
        await s.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/health/stale-stats")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_stale_stats_rejects_zero_threshold(pg_app):
    """``older_than_minutes`` is range-checked (``ge=1``).  Calling with
    0 must 422 — guards against a misconfigured scrape job sending the
    default and getting back the entire universe."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/v1/sync/health/stale-stats", params={"older_than_minutes": 0}
        )

    assert resp.status_code == 422, resp.text
