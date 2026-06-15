"""MODULE_PER_YEAR unit→module map resolution (regression, 2026-06-12).

A 49k-row production upload skipped every row with "No
carbon_report_module_id mapped for institutional_id=…" — the resolver
failed to produce a usable map and nothing in the suite pinned the
contract.  These tests pin it at the resolver level:

* existing (unit, report, module) trees resolve through ONE bulk join;
* units with no carbon_report for the year get one created
  (auto-creating its modules) and still land in the map;
* unknown unit codes are absent from the map but never poison the
  resolution of the valid ones.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from typing import Any, Dict

import pytest
from sqlmodel import col, select

from app.models.carbon_report import CarbonReportModule
from app.models.data_ingestion import EntityType
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.base_csv_provider import BaseCSVProvider

pytestmark = pytest.mark.asyncio

MODULE_TYPE = ModuleTypeEnum.headcount.value
YEAR = 2026


class _ResolverProvider(BaseCSVProvider):
    """Minimal concrete provider to drive _resolve_carbon_report_modules."""

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        return {}

    def _extract_kind_subkind_values(self, filtered_row, handlers):
        return ("kind", None)

    async def _resolve_handler_and_validate(
        self, filtered_row, factor, stats, row_idx, max_row_errors, setup_result
    ):
        return (None, None, None)


def _provider(session) -> _ResolverProvider:
    return _ResolverProvider(
        {"module_type_id": MODULE_TYPE, "year": YEAR},
        data_session=session,
    )


def _csv_for(*codes: str) -> str:
    rows = "\n".join(f"{c},someone-{i}" for i, c in enumerate(codes))
    return f"unit_institutional_id,name\n{rows}\n"


async def test_existing_tree_resolves_via_bulk_join(
    pg_session, make_unit, make_carbon_report, make_carbon_report_module
):
    units = [await make_unit(pg_session) for _ in range(3)]
    expected: Dict[str, int] = {}
    for unit in units:
        report = await make_carbon_report(pg_session, unit_id=unit.id, year=YEAR)
        module = await make_carbon_report_module(
            pg_session, carbon_report_id=report.id, module_type_id=MODULE_TYPE
        )
        expected[unit.institutional_id] = module.id
    await pg_session.commit()

    resolved = await _provider(pg_session)._resolve_carbon_report_modules(
        _csv_for(*expected.keys())
    )

    assert resolved == expected


async def test_missing_report_is_created_and_mapped(pg_session, make_unit):
    """The production-failure shape: unit exists, no carbon_report yet.
    Every CSV unit must still end up in the map (rows must NOT skip)."""
    unit = await make_unit(pg_session)
    await pg_session.commit()

    resolved = await _provider(pg_session)._resolve_carbon_report_modules(
        _csv_for(unit.institutional_id)
    )
    await pg_session.commit()

    assert unit.institutional_id in resolved
    module = (
        await pg_session.execute(
            select(CarbonReportModule).where(
                col(CarbonReportModule.id) == resolved[unit.institutional_id]
            )
        )
    ).scalar_one()
    assert module.module_type_id == MODULE_TYPE


async def test_unknown_units_skip_without_breaking_valid_ones(
    pg_session, make_unit, make_carbon_report, make_carbon_report_module
):
    unit = await make_unit(pg_session)
    report = await make_carbon_report(pg_session, unit_id=unit.id, year=YEAR)
    module = await make_carbon_report_module(
        pg_session, carbon_report_id=report.id, module_type_id=MODULE_TYPE
    )
    await pg_session.commit()

    resolved = await _provider(pg_session)._resolve_carbon_report_modules(
        _csv_for(unit.institutional_id, "GHOST-9999")
    )

    assert resolved[unit.institutional_id] == module.id
    assert "GHOST-9999" not in resolved


async def test_map_scoped_to_csv_units_only(
    pg_session, make_unit, make_carbon_report, make_carbon_report_module
):
    """Regression (2026-06-12): the bulk join sees EVERY unit with a
    report for the (year, module_type) — but the returned map must only
    contain the CSV's units, because the pre-import deletion runs over
    the whole map.  An unfiltered map made a 137-unit CSV wipe
    CSV-uploaded entries of all ~1.8k units for the year."""
    units = [await make_unit(pg_session) for _ in range(3)]
    modules = {}
    for unit in units:
        report = await make_carbon_report(pg_session, unit_id=unit.id, year=YEAR)
        module = await make_carbon_report_module(
            pg_session, carbon_report_id=report.id, module_type_id=MODULE_TYPE
        )
        modules[unit.institutional_id] = module.id
    await pg_session.commit()

    csv_unit = units[0].institutional_id
    resolved = await _provider(pg_session)._resolve_carbon_report_modules(
        _csv_for(csv_unit)
    )

    assert resolved == {csv_unit: modules[csv_unit]}
