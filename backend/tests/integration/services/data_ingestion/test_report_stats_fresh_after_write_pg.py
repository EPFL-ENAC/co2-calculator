"""Report stats must be fresh the moment an interactive write returns (#2050 J9).

The frontend fetches ``/v1/modules-stats/{id}/report-stats`` in the same
interaction as the write (visible in the dev waterfall, 2026-08-19), and that
endpoint returns the **persisted** ``carbon_reports.stats`` column. So the
report totals are part of what the caller reads back, and they cannot be
eventually consistent: a total that is missing the entry the user just added
is a wrong number that looks complete.

This pins the contract that #2050 J4's deferred rollup broke. Two ways it
broke, both fixed here:

1. ``fire_and_forget_or_defer_to_poller`` closes its coroutine unstarted when
   ``DISPATCH_JOBS_INLINE`` is false — every API pod, once the worker is
   enabled (``helm/templates/backend-deployment.yaml``) — on the documented
   assumption that a ``DataIngestionJob`` row exists for the poller. The
   rollup committed no such row, so the work vanished entirely.
2. Even dispatched correctly, the read races the write.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
from app.models.carbon_report import CarbonReport
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import emission_type_scope
from app.services.carbon_report_module_service import CarbonReportModuleService

pytestmark = pytest.mark.asyncio


async def test_report_stats_are_written_by_the_time_recompute_returns(
    pg_dsn, make_unit, make_carbon_report, make_carbon_report_module
):
    """``recompute_stats`` leaves the report's persisted stats up to date, in
    the same transaction — no dispatch, no window where a reader sees the old
    total.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            unit = await make_unit(session)
            report = await make_carbon_report(session, unit_id=unit.id, year=2025)
            module = await make_carbon_report_module(
                session,
                carbon_report_id=report.id,
                module_type_id=ModuleTypeEnum.process_emissions.value,
            )
            entry = DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
                data={"category": "refrigerant", "quantity_kg": 10.0},
            )
            session.add(entry)
            await session.flush()
            session.add(
                DataEntryEmission(
                    data_entry_id=entry.id,
                    emission_type_id=EmissionType.process_emissions.value,
                    kg_co2eq=42.0,
                    scope=emission_type_scope(EmissionType.process_emissions),
                )
            )
            await session.commit()
            report_id, module_id = report.id, module.id

        async with Sf() as session:
            await CarbonReportModuleService(session).recompute_stats(module_id)
            await session.commit()

        # A separate session, exactly as the follow-up GET would read it.
        async with Sf() as session:
            refreshed = await session.get(CarbonReport, report_id)
            assert refreshed is not None
            assert refreshed.stats, (
                "report.stats is empty right after the write returned — the "
                "read-after-write contract the frontend relies on is broken "
                "(#2050 J9)"
            )
            assert refreshed.last_updated is not None
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def api_pod_app(pg_dsn, monkeypatch):
    """The app wired as a **production API pod**: inline job dispatch OFF.

    ``helm/templates/backend-deployment.yaml`` sets DISPATCH_JOBS_INLINE=false
    on API pods whenever the worker is enabled. The setting defaults to true,
    which is why every local test passed while dev and stage dropped the work.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {"process_emissions": ["view", "edit"]}
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"
    fake_user.provider = 0
    fake_user.display_name = "Test User"
    fake_user.roles = []

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.check_module_permission_for_report", _allow
    )

    import app.tasks._background as background

    pod_settings = MagicMock()
    pod_settings.DISPATCH_JOBS_INLINE = False
    monkeypatch.setattr(background, "get_settings", lambda: pod_settings)

    yield {"factory": Sf, "engine": engine}

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_report_stats_are_fresh_after_an_interactive_create(
    api_pod_app, make_unit, make_carbon_report, make_carbon_report_module
):
    """POST an entry, then read the report's persisted stats exactly as the
    frontend's follow-up ``report-stats`` call does.
    """
    Sf = api_pod_app["factory"]
    async with Sf() as session:
        unit = await make_unit(session)
        report = await make_carbon_report(session, unit_id=unit.id, year=2025)
        await make_carbon_report_module(
            session,
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.process_emissions.value,
        )
        await session.commit()
        report_id = report.id

    url = f"/v1/carbon-reports/{report_id}/modules/process-emissions/process_emissions"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            url, json={"category": "refrigerant", "quantity_kg": 10.0}
        )
    assert resp.status_code in (200, 201), resp.text

    async with Sf() as session:
        refreshed = await session.get(CarbonReport, report_id)
        assert refreshed is not None
        assert refreshed.last_updated is not None, (
            "the report was never rolled up after an interactive create. On an "
            "API pod (DISPATCH_JOBS_INLINE=false) the deferred rollup's "
            "coroutine is closed unstarted and no job row exists for the "
            "poller, so report.stats stays stale forever (#2050 J9)."
        )
