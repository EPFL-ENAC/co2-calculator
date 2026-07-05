"""Purchase factor resolution against real Postgres + real repo semantics.

The selection-rule truth table itself (kind/subkind, override-key-first,
ambiguous-match) is now pinned against a faked repository in
``tests/unit/services/test_factor_resolver.py`` — that's the fast,
authoritative mirror.  What this module keeps that the unit tests can't
give: resolution through the real ``FactorRepository`` JSON-classification
query against real Postgres, seeded from the committed
``tests/fixtures/csv/purchases_common_factors_smoke.csv`` fixture, so a
regression in the actual JSON matching (not just the in-memory selection
rule) still gets caught.

The regression that motivated it: an entry with institutional code 23152900
and no additional code resolved to ``None`` because the rule excluded
single rows carrying an additional code — a shape the mocked unit factors
didn't reproduce.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import csv

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService

from .conftest import csv_fixture_path

_YEAR = 2025


def _factors_from_smoke_csv() -> list[Factor]:
    path = csv_fixture_path("purchases_common", "factors")
    factors = []
    with path.open() as fh:
        for row in csv.DictReader(fh):
            classification = {
                "purchase_institutional_code": row["purchase_institutional_code"],
                "purchase_additional_code": row["purchase_additional_code"],
                "currency": row["currency"],
            }
            factors.append(
                Factor(
                    emission_type_id=10000,
                    data_entry_type_id=DataEntryTypeEnum[
                        row["purchase_category"]
                    ].value,
                    classification=classification,
                    values={
                        "ef_kg_co2eq_per_currency": float(
                            row["ef_kg_co2eq_per_currency"]
                        ),
                        "currency": row["currency"],
                    },
                    year=_YEAR,
                )
            )
    return factors


@pytest_asyncio.fixture
async def session_factory(pg_dsn):
    engine = create_async_engine(pg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all(_factors_from_smoke_csv())
        await session.commit()
    yield factory
    await engine.dispose()


async def _resolve(
    session: AsyncSession, det: DataEntryTypeEnum, payload: dict
) -> Factor | None:
    handler = BaseModuleHandler.get_by_type(det)
    service = ModuleHandlerService(session)
    return await service.resolve_factor(handler, payload, det, year=_YEAR)


@pytest.mark.asyncio
async def test_pg_additional_code_wins_over_average_row(session_factory):
    """51100000 + LA05 → the 0.41 row, not the 0.455 average row."""
    async with session_factory() as session:
        result = await _resolve(
            session,
            DataEntryTypeEnum.biological_chemical_gaseous_product,
            {
                "purchase_institutional_code": "51100000",
                "purchase_additional_code": "LA05",
            },
        )
        assert result is not None
        assert result.values["ef_kg_co2eq_per_currency"] == 0.41


@pytest.mark.asyncio
async def test_pg_no_additional_code_picks_average_row(session_factory):
    """51100000 alone → the additional-code-less 0.455 average row."""
    async with session_factory() as session:
        result = await _resolve(
            session,
            DataEntryTypeEnum.biological_chemical_gaseous_product,
            {"purchase_institutional_code": "51100000"},
        )
        assert result is not None
        assert result.values["ef_kg_co2eq_per_currency"] == 0.455


@pytest.mark.asyncio
async def test_pg_single_row_with_code_is_authoritative(session_factory):
    """91111500 only exists with AA66 — it must still match (the 23152900 bug)."""
    async with session_factory() as session:
        result = await _resolve(
            session,
            DataEntryTypeEnum.services,
            {"purchase_institutional_code": "91111500"},
        )
        assert result is not None
        assert result.values["ef_kg_co2eq_per_currency"] == 0.21


@pytest.mark.asyncio
async def test_pg_unknown_additional_code_falls_back(session_factory):
    """Typo'd additional code → institutional rule still resolves."""
    async with session_factory() as session:
        result = await _resolve(
            session,
            DataEntryTypeEnum.biological_chemical_gaseous_product,
            {
                "purchase_institutional_code": "51100000",
                "purchase_additional_code": "NOPE",
            },
        )
        assert result is not None
        assert result.values["ef_kg_co2eq_per_currency"] == 0.455


@pytest.mark.asyncio
async def test_pg_unknown_institutional_code_yields_none(session_factory):
    async with session_factory() as session:
        result = await _resolve(
            session,
            DataEntryTypeEnum.services,
            {"purchase_institutional_code": "99999999"},
        )
        assert result is None


@pytest.mark.asyncio
async def test_pg_missing_institutional_code_yields_none(session_factory):
    """No ``purchase_institutional_code`` in the payload → no match.

    Pre-#1661 this raised ``ValueError`` from inside the resolution
    method itself.  That guard was dead weight in production: the
    manual-create workflow always runs ``handler.validate_create``
    (pydantic — ``PurchaseHandlerCreate.purchase_institutional_code``
    is a required ``str``) before any factor resolution is attempted,
    and CSV ingestion never calls this resolver at all (it has its own
    inline, silent-on-miss factors_map lookup). ``FactorResolver`` — the
    on-demand resolver this method now delegates to — treats a missing
    kind field as a plain miss, consistent with every other module.
    """
    async with session_factory() as session:
        result = await _resolve(
            session,
            DataEntryTypeEnum.services,
            {"purchase_additional_code": "AA66"},
        )
        assert result is None
