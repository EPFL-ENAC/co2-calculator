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
            CarbonReportModuleRepository._get_completion_status_from_progress("0/7")
            == ModuleStatus.NOT_STARTED
        )

    def test_in_progress(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("3/7")
            == ModuleStatus.IN_PROGRESS
        )

    def test_validated(self):
        assert (
            CarbonReportModuleRepository._get_completion_status_from_progress("7/7")
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
        assert await repo.delete(mod.id) is True
        assert await repo.get(mod.id) is None

    async def test_delete_nonexistent(self, db_session):
        repo = CarbonReportModuleRepository(db_session)
        assert await repo.delete(999) is False

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
        _user = await make_user(db_session)
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
        assert results[0]["module_status"] == ModuleStatus.VALIDATED

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
        _cr = await make_carbon_report(
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
        _cr = await make_carbon_report(
            db_session, unit_id=unit.id, year=2024, stats=None
        )
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

    async def test_basic_overview(
        self, db_session, make_unit, make_user, make_carbon_report
    ):
        _user = await make_user(db_session, institutional_id="SCIPER-P1")
        unit = await make_unit(
            db_session,
            name="LAB-O",
            principal_user_institutional_id="SCIPER-P1",
        )
        cr = await make_carbon_report(
            db_session,
            unit_id=unit.id,
            year=2024,
            completion_progress="3/7",
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
        _cr = await make_carbon_report(db_session, unit_id=unit.id, year=2024)
        repo = CarbonReportModuleRepository(db_session)
        # Filter for nonexistent units → should short-circuit
        result = await repo.get_reporting_overview(
            years=[2024], path_lvl4=["NONEXISTENT"]
        )
        assert result["total"] == 0
        assert result["data"] == []
