"""Statement budget for the module-detail GET (#2050 Track G2/J).

The observation, from the lead on dev (2026-08-19):
``GET /api/v1/carbon-reports/11604/modules/process-emissions/`` took **648ms**
for a module holding **one** entry and returning 947 bytes — on the same page
where the `POST` that created the entry took 85.7ms and the sibling
``modules/`` call took 80.9ms. So it is not connection checkout: the other
calls on that page pay the same checkout and answer in a fraction of the time.

Same rig as the write-path budget test: statements counted through the real
HTTP route on real Postgres, on psycopg3 because batching is driver-dependent.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum

YEAR = 2025

SELECT_RE = re.compile(r"^SELECT", re.IGNORECASE)
TAXONOMY_RE = re.compile(r"\bfactors\b|\bemission_type", re.IGNORECASE)


@dataclass
class StatementLog:
    statements: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.statements)

    @property
    def selects(self) -> int:
        return sum(1 for s in self.statements if SELECT_RE.match(s.strip()))

    def by_table(self) -> dict[str, int]:
        """Rough per-table tally — enough to see an N+1 without reading 40 lines."""
        counts: dict[str, int] = {}
        for statement in self.statements:
            match = re.search(
                r"\bFROM\s+([a-z_]+)|\bINTO\s+([a-z_]+)|\bUPDATE\s+([a-z_]+)",
                statement,
                re.IGNORECASE,
            )
            table = next((g for g in (match.groups() if match else ()) if g), "?")
            counts[table] = counts.get(table, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def breakdown(self) -> str:
        return f"total={self.total} selects={self.selects} {self.by_table()}"

    def numbered(self) -> str:
        return "\n".join(
            f"  {i:>2}. {' '.join(s.split())[:110]}"
            for i, s in enumerate(self.statements, 1)
        )


@contextmanager
def count_statements(engine):
    log = StatementLog()

    def listener(conn, cursor, statement, parameters, context, executemany):
        log.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        yield log
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth."""
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

    yield {"factory": Sf, "engine": engine}

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_one_entry_module(
    session, make_unit, make_carbon_report, make_carbon_report_module
) -> int:
    """A process-emissions module holding exactly one entry — the shape the
    dev observation was made on.
    """
    unit = await make_unit(session)
    report = await make_carbon_report(session, unit_id=unit.id, year=YEAR)
    module = await make_carbon_report_module(
        session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.process_emissions.value,
    )
    session.add(
        DataEntry(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            data={"category": "refrigerant", "quantity_kg": 10.0},
        )
    )
    await session.commit()
    if report.id is None:
        raise ValueError("seed did not assign a carbon_report_id")
    return report.id


@pytest.mark.asyncio
async def test_submodule_get_statement_budget(
    pg_app, make_unit, make_carbon_report, make_carbon_report_module
):
    """Measure what one *submodule* GET costs for a one-entry submodule.

    This is the 648ms call in the dev waterfall: Safari shows the last path
    segment in its Name column, so the row reading
    process_emissions under path .../modules/process-emissions/ is
    GET /{carbon_report_id}/modules/{module_id}/{submodule_id}, not the
    module GET beside it (80.9ms).
    """
    async with pg_app["factory"]() as session:
        carbon_report_id = await _seed_one_entry_module(
            session, make_unit, make_carbon_report, make_carbon_report_module
        )

    url = (
        f"/v1/carbon-reports/{carbon_report_id}/modules/process-emissions"
        "/process_emissions"
    )
    with count_statements(pg_app["engine"]) as log:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(url)

    print(f"\n>>> GET module: {log.breakdown()}\n{log.numbered()}\n")
    assert resp.status_code == 200, resp.text

    assert log.total <= STATEMENT_BUDGET, (
        f"one submodule GET issued {log.total} statements for a module holding a "
        f"single entry, budget is {STATEMENT_BUDGET} (#2050 Track J).\n"
        f"{log.breakdown()}\n{log.numbered()}"
    )


# Ratchet, measured on the fixture above. Lower it when the path gets cheaper;
# never raise it without a written reason in plan 2050.
STATEMENT_BUDGET = 12
