"""Tests for CarbonReportModuleRepository.

Covers CRUD operations, static helpers, and reporting queries
(get_usage_report, get_results_report, get_reporting_overview).
"""

import pytest

from app.core.constants import ModuleStatus
from app.models.module_type import ModuleTypeEnum
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository
from app.schemas.carbon_report import CarbonReportModuleCreate

# ---------------------------------------------------------------------------
# Static / pure methods
# ---------------------------------------------------------------------------


class TestSplitFilterValues:
    def test_mixed_values(self):
        ids, names = CarbonReportModuleRepository._split_filter_values(
            ["1", "LCBM", "42", "  ", "ENAC"]
        )
        assert ids == [1, 42]
        assert names == ["LCBM", "ENAC"]

    def test_none_input(self):
        ids, names = CarbonReportModuleRepository._split_filter_values(None)
        assert ids == []
        assert names == []

    def test_empty_list(self):
        ids, names = CarbonReportModuleRepository._split_filter_values([])
        assert ids == []
        assert names == []


class TestGetCompletionStatusFromProgress:
    def test_none(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress(None)
            == ModuleStatus.NOT_STARTED
        )

    def test_not_started(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("0/8")
            == ModuleStatus.NOT_STARTED
        )

    def test_in_progress(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("3/8")
            == ModuleStatus.IN_PROGRESS
        )

    def test_validated(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("8/8")
            == ModuleStatus.VALIDATED
        )

    def test_invalid_format(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("abc")
            == ModuleStatus.NOT_STARTED
        )

    def test_zero_total(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("0/0")
            == ModuleStatus.NOT_STARTED
        )


class TestMapModuleIdToName:
    def test_valid_id(self):
        repo = CarbonReportModuleRepository.__new__(CarbonReportModuleRepository)
        assert repo._map_module_id_to_name(1) == "headcount"
        assert repo._map_module_id_to_name(2) == "professional_travel"

    def test_none(self):
        repo = CarbonReportModuleRepository.__new__(CarbonReportModuleRepository)
        assert repo._map_module_id_to_name(None) == "—"

    def test_zero(self):
        repo = CarbonReportModuleRepository.__new__(CarbonReportModuleRepository)
        assert repo._map_module_id_to_name(0) == "—"


# ---------------------------------------------------------------------------
# CRUD tests (use db_session)
# ---------------------------------------------------------------------------


class TestScopeUnitIds:
    """cf -> institutional_code -> descendant subtree via path_institutional_code."""

    async def _build_enac_subtree(self, db_session, make_unit):
        # Anchor (lvl2) + descendants share the anchor code 12635 as a path token.
        anchor = await make_unit(
            db_session,
            institutional_code="12635",
            institutional_id="13030",
            level=2,
            path_institutional_code="10582 12635",
        )
        child = await make_unit(
            db_session,
            institutional_code="11435",
            institutional_id="13031",
            level=3,
            path_institutional_code="10582 12635 11435",
        )
        leaf = await make_unit(
            db_session,
            institutional_code="14270",
            institutional_id="13032",
            level=4,
            path_institutional_code="10582 12635 11435 14270",
        )
        other = await make_unit(
            db_session,
            institutional_code="99999",
            institutional_id="88888",
            level=2,
            path_institutional_code="10582 99999",
        )
        return anchor, child, leaf, other

    async def test_resolves_cf_to_self_and_descendants(self, db_session, make_unit):
        anchor, child, leaf, other = await self._build_enac_subtree(
            db_session, make_unit
        )
        repo = CarbonReportModuleRepository(db_session)
        ids = await repo._get_scope_unit_ids({"13030"})
        assert ids == {anchor.id, child.id, leaf.id}
        assert other.id not in ids

    async def test_unknown_cf_resolves_to_empty_not_all(self, db_session, make_unit):
        await self._build_enac_subtree(db_session, make_unit)
        repo = CarbonReportModuleRepository(db_session)
        # A scope cf with no matching unit must yield {} — never "all units".
        assert await repo._get_scope_unit_ids({"does-not-exist"}) == set()


class TestResolveHierarchyUnitIdsScope:
    """scope ∩ (affiliation ∪ lvl4) — the security clamp invariant.

    A scoped caller must always resolve to a concrete set, never None
    (None means "no constraint" → all units, a privilege escalation).
    """

    async def _subtree(self, db_session, make_unit):
        anchor = await make_unit(
            db_session,
            institutional_code="12635",
            institutional_id="13030",
            name="ENAC",
            level=2,
            path_institutional_code="10582 12635",
        )
        leaf = await make_unit(
            db_session,
            institutional_code="14270",
            institutional_id="13032",
            name="ENAC-IT4R",
            level=4,
            path_institutional_code="10582 12635 11435 14270",
        )
        outside = await make_unit(
            db_session,
            institutional_code="99999",
            institutional_id="88888",
            name="OUTSIDE",
            level=4,
            path_institutional_code="10582 99999",
        )
        return anchor, leaf, outside

    async def test_global_no_filters_returns_none(self, db_session, make_unit):
        await self._subtree(db_session, make_unit)
        repo = CarbonReportModuleRepository(db_session)
        result = await repo._resolve_hierarchy_unit_ids(is_global=True)
        assert result is None

    async def test_scoped_no_filters_returns_scope_set_not_none(
        self, db_session, make_unit
    ):
        anchor, leaf, _ = await self._subtree(db_session, make_unit)
        repo = CarbonReportModuleRepository(db_session)
        result = await repo._resolve_hierarchy_unit_ids(
            is_global=False, scope_cfs={"13030"}
        )
        assert result == {anchor.id, leaf.id}

    async def test_scoped_intersects_in_scope_filter(self, db_session, make_unit):
        anchor, leaf, _ = await self._subtree(db_session, make_unit)
        repo = CarbonReportModuleRepository(db_session)
        result = await repo._resolve_hierarchy_unit_ids(
            path_lvl4=["ENAC-IT4R"], is_global=False, scope_cfs={"13030"}
        )
        assert result == {leaf.id}

    async def test_scoped_out_of_scope_filter_yields_empty(self, db_session, make_unit):
        await self._subtree(db_session, make_unit)
        repo = CarbonReportModuleRepository(db_session)
        result = await repo._resolve_hierarchy_unit_ids(
            path_lvl4=["OUTSIDE"], is_global=False, scope_cfs={"13030"}
        )
        assert result == set()

    async def test_global_with_filters_ignores_scope(self, db_session, make_unit):
        _, _, outside = await self._subtree(db_session, make_unit)
        repo = CarbonReportModuleRepository(db_session)
        result = await repo._resolve_hierarchy_unit_ids(
            path_lvl4=["OUTSIDE"], is_global=True
        )
        assert result == {outside.id}


class TestCRUD:
    async def test_create(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.headcount)
        assert mod.id is not None
        assert mod.carbon_report_id == cr.id
        assert mod.module_type_id == ModuleTypeEnum.headcount
        assert mod.status == ModuleStatus.NOT_STARTED

    async def test_get(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.headcount)
        fetched = await repo.get(mod.id)
        assert fetched is not None
        assert fetched.id == mod.id

    async def test_get_nonexistent(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        assert await repo.get(999) is None

    async def test_get_module_type(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.buildings)
        result = await repo.get_module_type(mod.id)
        assert result == ModuleTypeEnum.buildings

    async def test_get_module_type_nonexistent(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        assert await repo.get_module_type(999) is None

    async def test_get_by_report_and_module_type(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.purchase)
        fetched = await repo.get_by_report_and_module_type(
            cr.id, ModuleTypeEnum.purchase
        )
        assert fetched is not None
        assert fetched.id == mod.id

    async def test_list_by_report(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(cr.id, ModuleTypeEnum.headcount)
        await repo.create(cr.id, ModuleTypeEnum.buildings)
        mods = await repo.list_by_report(cr.id)
        assert len(mods) == 2
        assert mods[0].module_type_id < mods[1].module_type_id  # ordered

    async def test_bulk_create(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        creates = [
            CarbonReportModuleCreate(
                carbon_report_id=cr.id, module_type_id=mt, status=0
            )
            for mt in [ModuleTypeEnum.headcount, ModuleTypeEnum.buildings]
        ]
        mods = await repo.bulk_create(creates)
        assert len(mods) == 2
        assert all(m.id is not None for m in mods)

    async def test_bulk_create_of_carbon_report(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mods = await repo.bulk_create_carbon_report_modules_of_carbon_report(
            cr.id, [1, 2, 3]
        )
        assert len(mods) == 3

    async def test_update_status(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(cr.id, ModuleTypeEnum.headcount)
        updated = await repo.update_status(
            cr.id, ModuleTypeEnum.headcount, ModuleStatus.VALIDATED
        )
        assert updated is not None
        assert updated.status == ModuleStatus.VALIDATED

    async def test_update_status_nonexistent(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        assert await repo.update_status(999, 1, ModuleStatus.VALIDATED) is None

    async def test_update_stats(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.headcount)
        await repo.update_stats(mod.id, {"total": 500})
        refreshed = await repo.get(mod.id)
        assert refreshed.stats == {"total": 500}

    async def test_update_stats_nonexistent(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        # Should not raise, just logs warning
        await repo.update_stats(999, {"total": 0})

    async def test_delete(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.headcount)
        deleted = await repo.delete(mod.id)
        assert deleted is True
        assert await repo.get(mod.id) is None

    async def test_delete_nonexistent(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        deleted = await repo.delete(999)
        assert deleted is False

    async def test_delete_by_report(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id)
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(cr.id, ModuleTypeEnum.headcount)
        await repo.create(cr.id, ModuleTypeEnum.buildings)
        count = await repo.delete_by_report(cr.id)
        assert count == 2
        assert await repo.list_by_report(cr.id) == []

    async def test_get_by_year_and_unit(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)
        mod = await repo.create(cr.id, ModuleTypeEnum.headcount)
        fetched = await repo.get_by_year_and_unit(
            2024, unit.id, ModuleTypeEnum.headcount
        )
        assert fetched is not None
        assert fetched.id == mod.id

    async def test_get_by_year_and_unit_not_found(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        assert (
            await repo.get_by_year_and_unit(2024, 999, ModuleTypeEnum.headcount) is None
        )


# ---------------------------------------------------------------------------
# Reporting queries
# ---------------------------------------------------------------------------


class TestGetUsageReport:
    async def test_basic_usage_report(
        self, db_session, make_unit, make_user, make_carbon_report
    ):
        unit = await make_unit(db_session, institutional_id="CF-100", name="LAB-A")
        await make_user(db_session)
        cr = await make_carbon_report(db_session, unit_id=unit.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(
            cr.id, ModuleTypeEnum.headcount, status=ModuleStatus.VALIDATED
        )
        await repo.create(
            cr.id, ModuleTypeEnum.buildings, status=ModuleStatus.NOT_STARTED
        )

        results = await repo.get_usage_report(years=[2024])
        assert len(results) == 2
        assert results[0]["module_name"] == "headcount"
        assert results[0]["module_status"] == "VALIDATED"

    async def test_empty_result_with_no_data(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        results = await repo.get_usage_report(years=[2024])
        assert results == []

    async def test_hierarchy_filter_no_match(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session, name="LAB-X")
        cr = await make_carbon_report(db_session, unit_id=unit.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(cr.id, ModuleTypeEnum.headcount)
        # Filter for a unit that doesn't exist
        results = await repo.get_usage_report(years=[2024], path_lvl4=["NONEXISTENT"])
        assert results == []

    async def test_module_filter(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session, name="LAB-F")
        cr = await make_carbon_report(db_session, unit_id=unit.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(
            cr.id, ModuleTypeEnum.headcount, status=ModuleStatus.VALIDATED
        )
        await repo.create(
            cr.id, ModuleTypeEnum.buildings, status=ModuleStatus.NOT_STARTED
        )
        # Filter for headcount with status 2 (VALIDATED)
        results = await repo.get_usage_report(years=[2024], modules=["headcount:2"])
        assert len(results) == 1
        assert results[0]["module_name"] == "headcount"

    async def test_invalid_module_filter(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        with pytest.raises(ValueError, match="Invalid module type"):
            await repo.get_usage_report(years=[2024], modules=["nonexistent"])


class TestGetResultsReport:
    async def test_basic_results_report(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session, institutional_id="CF-200", name="LAB-R")
        await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2024,
            stats={
                "scope1": 100,
                "scope2": 200,
                "scope3": 300,
                "total": 600,
                "by_emission_type": {"10000": 50, "50000": 150},
            },
        )
        repo = CarbonReportModuleRepository(db_session)
        results = await repo.get_results_report(years=[2024])
        assert len(results) == 1
        row = results[0]
        assert row["scope1"] == 100
        assert row["total"] == 600
        # Emission types are flattened with underscored names
        assert "food" in row
        assert "professional_travel" in row

    async def test_empty_stats(self, db_session, make_unit, make_carbon_report):
        unit = await make_unit(db_session, name="LAB-E")
        await make_carbon_report(db_session, unit_id=unit.id, year=2024, stats=None)
        repo = CarbonReportModuleRepository(db_session)
        results = await repo.get_results_report(years=[2024])
        assert len(results) == 1
        assert results[0]["scope1"] is None


class TestGetReportingOverview:
    async def test_requires_years(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        with pytest.raises(ValueError, match="At least one year"):
            await repo.get_reporting_overview()

    async def test_empty_data(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        result = await repo.get_reporting_overview(years=[2024])
        assert result["total"] == 0
        assert result["data"] == []

    async def test_scoped_overview_clamps_to_subtree(
        self, db_session, make_unit, make_carbon_report
    ):
        anchor = await make_unit(
            db_session,
            institutional_code="12635",
            institutional_id="13030",
            name="ENAC",
            level=2,
            path_institutional_code="10582 12635",
        )
        leaf = await make_unit(
            db_session,
            institutional_code="14270",
            institutional_id="13032",
            name="ENAC-IT4R",
            level=4,
            path_institutional_code="10582 12635 11435 14270",
        )
        outside = await make_unit(
            db_session,
            institutional_code="99999",
            institutional_id="88888",
            name="OUTSIDE",
            level=4,
            path_institutional_code="10582 99999",
        )
        for u in (anchor, leaf, outside):
            await make_carbon_report(db_session, unit_id=u.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)

        result = await repo.get_reporting_overview(
            years=[2024], is_global=False, scope_cfs={"13030"}
        )
        names = {row["unit_name"] for row in result["data"]}
        assert names == {"ENAC", "ENAC-IT4R"}
        assert "OUTSIDE" not in names

        # An out-of-scope lvl4 filter intersects to empty.
        empty = await repo.get_reporting_overview(
            years=[2024],
            path_lvl4=["OUTSIDE"],
            is_global=False,
            scope_cfs={"13030"},
        )
        assert empty["total"] == 0

    async def test_basic_overview(
        self, db_session, make_unit, make_user, make_carbon_report
    ):
        await make_user(db_session, institutional_id="SCIPER-P1")
        unit = await make_unit(
            db_session,
            name="LAB-O",
            principal_user_institutional_id="SCIPER-P1",
        )
        cr = await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2024,
            completion_progress="3/8",
            overall_status=ModuleStatus.IN_PROGRESS,
        )
        repo = CarbonReportModuleRepository(db_session)
        await repo.create(
            cr.id, ModuleTypeEnum.headcount, status=ModuleStatus.VALIDATED
        )

        result = await repo.get_reporting_overview(years=[2024])
        assert result["total"] == 1
        assert len(result["data"]) == 1
        assert result["data"][0]["unit_name"] == "LAB-O"
        assert result["in_progress_units_count"] == 1

    async def test_hierarchy_filter_empty_resolves(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session, name="LAB-HF")
        await make_carbon_report(db_session, unit_id=unit.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)
        # Filter for nonexistent units → should short-circuit
        result = await repo.get_reporting_overview(
            years=[2024], path_lvl4=["NONEXISTENT"]
        )
        assert result["total"] == 0
        assert result["data"] == []

    async def test_multi_year_counts_distinct_units(
        self, db_session, make_unit, make_carbon_report
    ):
        # One unit with a CarbonReport in each of the two selected years.
        # The (Unit JOIN CarbonReport) cardinality is 2, but the unit count
        # exposed to the UI must stay at 1 — otherwise the status cards and
        # table total double when multiple years are selected.
        unit = await make_unit(db_session, name="LAB-MY")
        cr_2024 = await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2024,
            overall_status=ModuleStatus.VALIDATED,
        )
        await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2025,
            overall_status=ModuleStatus.IN_PROGRESS,
            carbon_project_id=cr_2024.carbon_project_id,
        )
        repo = CarbonReportModuleRepository(db_session)
        result = await repo.get_reporting_overview(years=[2024, 2025])

        assert result["total"] == 1
        assert result["total_units_count"] == 1
        # Only 1 of 2 selected years is VALIDATED → IN_PROGRESS bucket
        # (matches the "1/2" row helper output).
        assert result["validated_units_count"] == 0
        assert result["in_progress_units_count"] == 1
        assert result["not_started_units_count"] == 0

    async def test_multi_year_all_validated_buckets_as_validated(
        self, db_session, make_unit, make_carbon_report
    ):
        unit = await make_unit(db_session, name="LAB-MYV")
        cr_2024 = await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2024,
            overall_status=ModuleStatus.VALIDATED,
        )
        await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2025,
            overall_status=ModuleStatus.VALIDATED,
            carbon_project_id=cr_2024.carbon_project_id,
        )
        repo = CarbonReportModuleRepository(db_session)
        result = await repo.get_reporting_overview(years=[2024, 2025])

        assert result["total_units_count"] == 1
        assert result["validated_units_count"] == 1
        assert result["in_progress_units_count"] == 0
        assert result["not_started_units_count"] == 0
