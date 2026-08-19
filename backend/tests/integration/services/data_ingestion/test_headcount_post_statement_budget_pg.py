"""Statement budget for the interactive headcount-member write (#2050 J4).

The question this answers, from the lead: *"we POST a new data_entry for
headcount_member and it does the following ... that's like way way too many
span/statement and sql statements; my guidelines is like 2-3 statements max
per http request."*

Measured, not estimated — and measured on **Postgres**, deliberately. The
existing SQLite harness
(``tests/unit/services/test_simulator_plan_reference_year_perf.py``) says
why: ``session.add_all`` + ``flush`` issues one INSERT per row on SQLite but
batches on Postgres, so a SQLite count would inflate the emission INSERTs
and confirm the wrong story about where the cost is.

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
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions.taxonomy import EmissionType

YEAR = 2025

# Mirrors test_headcount_pg.py's ``_HEADCOUNT_LEAVES`` — the three Strategy-B
# roots a member entry resolves (food / waste / commuting). Seeded so the POST
# actually computes emissions; without factors the write short-circuits and
# measures nothing interesting.
_HEADCOUNT_LEAVES: list[tuple[str, str, EmissionType, float, float]] = [
    ("food", "vegetarian", EmissionType.food__vegetarian, 1.0, 100.0),
    (
        "waste",
        "incineration",
        EmissionType.waste__incineration__domestic_waste,
        0.5,
        50.0,
    ),
    (
        "commuting",
        "public_transport",
        EmissionType.commuting__public_transport,
        0.2,
        200.0,
    ),
]

FACTOR_RE = re.compile(r"\bfactors\b", re.IGNORECASE)
EMISSION_RE = re.compile(r"\bdata_entry_emissions\b", re.IGNORECASE)
SELECT_RE = re.compile(r"^SELECT", re.IGNORECASE)


@dataclass
class StatementLog:
    """Statements issued during a measured block."""

    statements: list[str] = field(default_factory=list)
    params: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.statements)

    @property
    def distinct_factor_lookups(self) -> int:
        """Distinct (statement, parameters) pairs against ``factors``.

        The discriminator between "the same query repeated" (a memo fixes it)
        and "a different query per emission leaf" (only one combined query
        fixes it).
        """
        return len(
            {
                (s, p)
                for s, p in zip(self.statements, self.params, strict=True)
                if FACTOR_RE.search(s)
            }
        )

    @property
    def selects(self) -> int:
        return sum(1 for s in self.statements if SELECT_RE.match(s.strip()))

    @property
    def factor_lookups(self) -> int:
        return sum(1 for s in self.statements if FACTOR_RE.search(s))

    @property
    def emission_statements(self) -> int:
        return sum(1 for s in self.statements if EMISSION_RE.search(s))

    def breakdown(self) -> str:
        return (
            f"total={self.total} selects={self.selects} "
            f"factor_lookups={self.factor_lookups} "
            f"distinct_factor_lookups={self.distinct_factor_lookups} "
            f"emission_statements={self.emission_statements}"
        )

    def numbered(self) -> str:
        return "\n".join(
            f"  {i:>2}. {' '.join(s.split())[:110]}"
            for i, s in enumerate(self.statements, 1)
        )


@contextmanager
def count_statements(engine):
    """Count SQL statements issued by the wrapped block.

    Registers on ``engine.sync_engine``: DBAPI-level events fire on the sync
    engine backing an async one, regardless of the async driver wrapping it.
    """
    log = StatementLog()

    def listener(conn, cursor, statement, parameters, context, executemany):
        log.statements.append(statement)
        log.params.append(repr(parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        yield log
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    Mirrors ``test_recompute_stats_endpoint_pg.py``'s fixture of the same
    name, plus the headcount module permissions this route gates on.
    """
    # psycopg3, not the conftest's asyncpg: app/db.py forces
    # postgresql+psycopg in production, and the driver is not cosmetic here.
    # Statement batching (insertmanyvalues) is driver-dependent, so counting
    # on the wrong driver would measure the wrong thing — and asyncpg also
    # rejects the tz-aware datetime the audit writer hands to
    # audit_documents.changed_at (TIMESTAMP WITHOUT TIME ZONE), which psycopg
    # accepts by dropping the tzinfo.
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {"headcount": ["view", "edit"]}
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"
    fake_user.provider = 0
    # The workflow validates the caller into UserRead, so every field it
    # reads has to be a real value, not a MagicMock attribute.
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
    # The route gates on the module permission decision, not on roles.
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.check_module_permission_for_report",
        _allow,
    )

    yield {"factory": Sf, "engine": engine}

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed(
    session: AsyncSession, make_unit, make_carbon_report, make_carbon_report_module
) -> int:
    """A headcount module with the three member factors seeded, ready to POST
    into. Returns the carbon_report_id (the route is identity-addressed).

    Uses the shared factories (``tests/conftest.py``) rather than building the
    models here — they already carry the not-null columns.
    """
    unit = await make_unit(session)
    report = await make_carbon_report(session, unit_id=unit.id, year=YEAR)

    await make_carbon_report_module(
        session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.headcount.value,
    )
    session.add_all(
        [
            Factor(
                emission_type_id=emission.value,
                data_entry_type_id=DataEntryTypeEnum.member.value,
                classification={
                    "headcount_category": category,
                    "headcount_class": klass,
                },
                values={
                    "ef_kg_co2eq_per_unit": ef,
                    "number_of_unit_per_fte": multiplier,
                },
                year=YEAR,
            )
            for category, klass, emission, ef, multiplier in _HEADCOUNT_LEAVES
        ]
    )
    await session.commit()
    if report.id is None:
        raise ValueError("seed did not assign a carbon_report_id")
    return report.id


@pytest.mark.asyncio
async def test_headcount_member_post_statement_budget(
    pg_app, make_unit, make_carbon_report, make_carbon_report_module
):
    """Measure — and pin — the statements one interactive member POST costs.

    This is the measurement that decides whether the write path needs an
    async workflow or just needs the caches the bulk paths already pass. The
    budget below is a ratchet: it may come down as the path is batched, and
    it must never silently go up.
    """
    async with pg_app["factory"]() as session:
        carbon_report_id = await _seed(
            session, make_unit, make_carbon_report, make_carbon_report_module
        )

    payload = {
        "name": "Test Member",
        "user_institutional_id": "M-001",
        "sius_code": "51",
        "fte": 0.8,
        "headcount_category": "food",
        "headcount_class": "vegetarian",
    }

    with count_statements(pg_app["engine"]) as log:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"/v1/carbon-reports/{carbon_report_id}/modules/headcount/member",
                json=payload,
            )

    print(f"\n>>> POST member: {log.breakdown()}\n{log.numbered()}\n")
    assert resp.status_code in (200, 201), resp.text

    # A write that must return a recomputed total cannot reach the 2-3
    # statements a read can: permission/identity resolve, the entry INSERT,
    # the emissions INSERT, and this module's stats refresh are all
    # irreducible. What is *not* irreducible is per-emission-type factor
    # resolution — the bulk paths pass a shared FactorResolver and factor
    # query cache, and this path passes none (#2050 J4).
    assert log.total <= STATEMENT_BUDGET, (
        f"one member POST issued {log.total} statements, budget is "
        f"{STATEMENT_BUDGET} (#2050 J4).\n{log.breakdown()}\n{log.numbered()}"
    )
    assert log.factor_lookups <= FACTOR_LOOKUP_BUDGET, (
        f"one member POST issued {log.factor_lookups} factor lookups for "
        f"{len(_HEADCOUNT_LEAVES)} emission leaves, budget is "
        f"{FACTOR_LOOKUP_BUDGET}. Factor resolution must not scale with the "
        f"number of emission types on the entry (#2050 J4).\n{log.numbered()}"
    )


# Ratchets, measured on the seeded fixture above. Lower them when the path
# gets cheaper; never raise them without a written reason in plan 2050.
#
# Baseline before #2050 J4: total=50, factor_lookups=24 for an entry with
# three emission leaves — eight factor queries per leaf, because Strategy B
# walks a progressive fallback chain (B1..B4) and _fetch_factors memoizes it
# only when the caller passes a factor_query_cache, which every bulk path
# does and no interactive path did.
STATEMENT_BUDGET = 25
# One per emission leaf is the ceiling worth defending: factor resolution
# must not scale with the fallback chain's depth.
FACTOR_LOOKUP_BUDGET = 3
