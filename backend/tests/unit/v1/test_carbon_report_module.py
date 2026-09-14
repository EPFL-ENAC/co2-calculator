"""Unit tests for carbon_report_module endpoint helpers and list_headcount_members.

Covers:
- resolve_report_module / get_module_id_for_unit_year helpers
- list_headcount_members: permission gate, data-level scope, role-priority fix
- pick_role_for_institutional_id (role_priority module)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.carbon_report_module as crm
from app.core.constants import ModuleStatus
from app.core.role_priority import pick_role_for_institutional_id, role_priority_case
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import GlobalScope, OwnScope, Role, RoleName, UnitScope
from app.schemas.carbon_report import CarbonReportModuleRead, CarbonReportRead

# ── Helpers ───────────────────────────────────────────────────────────────────

UNIT_IID = "10208"


def _user(institutional_id="11111", roles=None):
    u = MagicMock()
    u.id = 1
    u.email = "test@example.com"
    u.institutional_id = institutional_id
    u.roles = roles or []
    return u


def _principal(unit_iid=UNIT_IID):
    return Role(
        role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id=unit_iid)
    )


def _std(unit_iid=UNIT_IID):
    return Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id=unit_iid))


def _global():
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _mock_db(unit_iid=UNIT_IID, unit_found=True):
    db = MagicMock()
    unit = MagicMock()
    unit.institutional_id = unit_iid
    db.get = AsyncMock(return_value=unit if unit_found else None)
    return db


def _resolved(module_id=1, unit_id=1, year=2024):
    """(report, module) pair as resolve_report_module would return them."""
    report = MagicMock()
    report.unit_id = unit_id
    report.year = year
    module = MagicMock()
    module.id = module_id
    return report, module


# ── resolve_report_module ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_report_module_returns_pair():
    # Real read models, not MagicMocks: resolve_report_module now projects
    # them out of a validated WriteScope (#2050 J4), so a mock with
    # MagicMock attributes would fail validation rather than pass through.
    db = MagicMock()
    report = CarbonReportRead(id=1, year=2025, unit_id=1, carbon_project_id=None)
    module = CarbonReportModuleRead(
        id=42,
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.headcount.value,
        status=ModuleStatus.IN_PROGRESS,
    )
    report_service = MagicMock()
    report_service.get = AsyncMock(return_value=report)
    module_service = MagicMock()
    module_service.get_module = AsyncMock(return_value=module)

    with (
        patch.object(crm, "CarbonReportService", return_value=report_service),
        patch.object(crm, "CarbonReportModuleService", return_value=module_service),
    ):
        got_report, got_module = await crm.resolve_report_module(
            1, "headcount", db, _user()
        )

    assert got_report.id == report.id
    assert got_module.id == 42


@pytest.mark.asyncio
async def test_resolve_report_module_raises_404_when_report_missing():
    db = MagicMock()
    report_service = MagicMock()
    report_service.get = AsyncMock(return_value=None)

    with patch.object(crm, "CarbonReportService", return_value=report_service):
        with pytest.raises(HTTPException) as exc:
            await crm.resolve_report_module(1, "headcount", db, _user())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_report_module_raises_404_when_module_missing():
    db = MagicMock()
    report = MagicMock()
    report.carbon_project_id = None
    report_service = MagicMock()
    report_service.get = AsyncMock(return_value=report)
    module_service = MagicMock()
    module_service.get_module = AsyncMock(return_value=None)

    with (
        patch.object(crm, "CarbonReportService", return_value=report_service),
        patch.object(crm, "CarbonReportModuleService", return_value=module_service),
    ):
        with pytest.raises(HTTPException) as exc:
            await crm.resolve_report_module(1, "headcount", db, _user())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_report_module_raises_404_for_unknown_module_slug():
    db = MagicMock()
    report = MagicMock()
    report.carbon_project_id = None
    report_service = MagicMock()
    report_service.get = AsyncMock(return_value=report)

    with patch.object(crm, "CarbonReportService", return_value=report_service):
        with pytest.raises(HTTPException) as exc:
            await crm.resolve_report_module(1, "not-a-module", db, _user())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_module_id_for_unit_year_returns_int():
    db = MagicMock()
    mock_module = MagicMock()
    mock_module.id = 7
    service = MagicMock()
    service.get_carbon_report_by_year_and_unit = AsyncMock(return_value=mock_module)

    with patch.object(crm, "CarbonReportModuleService", return_value=service):
        result = await crm.get_module_id_for_unit_year(
            1, 2024, ModuleTypeEnum.headcount, db
        )

    assert result == 7


@pytest.mark.asyncio
async def test_get_module_id_for_unit_year_maps_valueerror_to_http_404():
    """The service raises ValueError when no module exists; the combine loop
    catches only HTTPException, so this helper must translate it (else 500).
    """
    db = MagicMock()
    service = MagicMock()
    service.get_carbon_report_by_year_and_unit = AsyncMock(
        side_effect=ValueError("no module")
    )

    with patch.object(crm, "CarbonReportModuleService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await crm.get_module_id_for_unit_year(
                99, 2024, ModuleTypeEnum.headcount, db
            )

    assert exc.value.status_code == 404


# ── list_headcount_members: permission gate ───────────────────────────────────


@pytest.mark.asyncio
async def test_list_headcount_members_403_when_no_permission():
    user = _user(roles=[])
    db = _mock_db()

    async def deny_all(u, mod, action, **_kwargs):
        return {"allow": False}

    with (
        patch.object(crm, "resolve_report_module", AsyncMock(return_value=_resolved())),
        patch.object(crm, "get_module_permission_decision", side_effect=deny_all),
    ):
        with pytest.raises(HTTPException) as exc:
            await crm.list_headcount_members(1, db=db, current_user=user)

    assert exc.value.status_code == 403
    assert "Permission denied" in exc.value.detail


# ── list_headcount_members: full access paths ─────────────────────────────────


@pytest.mark.asyncio
async def test_list_headcount_members_principal_for_unit_sees_all():
    user = _user("11111", [_principal(UNIT_IID)])
    db = _mock_db(UNIT_IID)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_headcount(u, mod, action, **_kwargs):
        return {"allow": mod == "headcount"}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)

    with (
        patch.object(
            crm, "get_module_permission_decision", side_effect=allow_headcount
        ),
        patch.object(crm, "resolve_report_module", AsyncMock(return_value=_resolved())),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, db=db, current_user=user)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_headcount_members_global_role_sees_all():
    user = _user("11111", [_global()])
    db = _mock_db(UNIT_IID)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_all(u, mod, action, **_kwargs):
        return {"allow": True}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)

    with (
        patch.object(crm, "get_module_permission_decision", side_effect=allow_all),
        patch.object(crm, "resolve_report_module", AsyncMock(return_value=_resolved())),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, db=db, current_user=user)

    assert len(result) == 2


# ── list_headcount_members: restricted access paths ──────────────────────────


@pytest.mark.asyncio
async def test_list_headcount_members_std_user_sees_only_own():
    user = _user("11111", [_std(UNIT_IID)])
    db = _mock_db(UNIT_IID)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_travel(u, mod, action, **_kwargs):
        return {"allow": mod == "professional-travel"}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)
    svc.get_member_by_institutional_id = AsyncMock(
        return_value={"institutional_id": "11111", "name": "A"}
    )

    with (
        patch.object(crm, "get_module_permission_decision", side_effect=allow_travel),
        patch.object(crm, "resolve_report_module", AsyncMock(return_value=_resolved())),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, db=db, current_user=user)

    assert len(result) == 1
    assert result[0].institutional_id == "11111"


@pytest.mark.asyncio
async def test_list_headcount_members_principal_other_unit_sees_only_own():
    """Principal of unit B accessing unit A sees only their own record
    (role priority).
    """
    user = _user("11111", [_principal("99999"), _std(UNIT_IID)])
    db = _mock_db(UNIT_IID)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_headcount(u, mod, action, **_kwargs):
        return {"allow": mod == "headcount"}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)
    svc.get_member_by_institutional_id = AsyncMock(
        return_value={"institutional_id": "11111", "name": "A"}
    )

    with (
        patch.object(
            crm, "get_module_permission_decision", side_effect=allow_headcount
        ),
        patch.object(crm, "resolve_report_module", AsyncMock(return_value=_resolved())),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, db=db, current_user=user)

    assert len(result) == 1
    assert result[0].institutional_id == "11111"


@pytest.mark.asyncio
async def test_list_headcount_members_404_when_unit_missing():
    """Missing unit row raises 404 — the gate needs the unit's institutional_id
    to scope the permission lookup, so we can't continue without it.
    """
    user = _user("11111", [_principal(UNIT_IID)])
    db = _mock_db(unit_found=False)

    async def allow_headcount(u, mod, action, **_kwargs):
        return {"allow": mod == "headcount"}

    with (
        patch.object(crm, "resolve_report_module", AsyncMock(return_value=_resolved())),
        patch.object(
            crm, "get_module_permission_decision", side_effect=allow_headcount
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await crm.list_headcount_members(1, db=db, current_user=user)

    assert exc.value.status_code == 404


# ── pick_role_for_institutional_id ────────────────────────────────────────────


def test_pick_role_returns_none_for_empty_roles():
    assert pick_role_for_institutional_id([], UNIT_IID) is None


def test_pick_role_returns_none_when_no_matching_unit():
    roles = [_principal("99999")]
    assert pick_role_for_institutional_id(roles, UNIT_IID) is None


def test_pick_role_returns_principal_for_matching_unit():
    roles = [_principal(UNIT_IID)]
    assert (
        pick_role_for_institutional_id(roles, UNIT_IID) == RoleName.CO2_USER_PRINCIPAL
    )


def test_pick_role_returns_std_when_only_std():
    roles = [_std(UNIT_IID)]
    assert pick_role_for_institutional_id(roles, UNIT_IID) == RoleName.CO2_USER_STD


def test_pick_role_prefers_principal_over_std_for_same_unit():
    """Principal has higher priority (lower number) than STD."""
    roles = [_std(UNIT_IID), _principal(UNIT_IID)]
    assert (
        pick_role_for_institutional_id(roles, UNIT_IID) == RoleName.CO2_USER_PRINCIPAL
    )


def test_pick_role_ignores_global_scope_roles():
    """GlobalScope roles don't have institutional_id — should not match."""
    roles = [_global()]
    assert pick_role_for_institutional_id(roles, UNIT_IID) is None


def test_pick_role_ignores_other_unit():
    """Roles for a different unit should not match."""
    roles = [_principal("99999"), _std("88888")]
    assert pick_role_for_institutional_id(roles, UNIT_IID) is None


def test_role_priority_case_produces_sqlalchemy_case():
    column = MagicMock()
    result = role_priority_case(column)
    # Just verifies the function runs and returns something (SQLAlchemy case obj)
    assert result is not None


# ── _has_global_or_principal_access_for_unit ──────────────────────────────────


class TestHasGlobalOrPrincipalAccess:
    def test_global_role_returns_true(self):
        user = _user(roles=[_global()])
        assert crm._has_global_or_principal_access_for_unit(user, None) is True

    def test_principal_for_matching_unit(self):
        user = _user(roles=[_principal(UNIT_IID)])
        unit = MagicMock()
        unit.institutional_id = UNIT_IID
        assert crm._has_global_or_principal_access_for_unit(user, unit) is True

    def test_std_for_matching_unit(self):
        user = _user(roles=[_std(UNIT_IID)])
        unit = MagicMock()
        unit.institutional_id = UNIT_IID
        assert crm._has_global_or_principal_access_for_unit(user, unit) is False

    def test_unit_none(self):
        user = _user(roles=[_principal(UNIT_IID)])
        assert crm._has_global_or_principal_access_for_unit(user, None) is False

    def test_unit_no_institutional_id(self):
        user = _user(roles=[_principal(UNIT_IID)])
        unit = MagicMock()
        unit.institutional_id = None
        assert crm._has_global_or_principal_access_for_unit(user, unit) is False

    def test_no_roles(self):
        user = _user(roles=[])
        unit = MagicMock()
        unit.institutional_id = UNIT_IID
        assert crm._has_global_or_principal_access_for_unit(user, unit) is False


# ── _get_professional_travel_institutional_id_filter ──────────────────────────


class TestGetProfessionalTravelFilter:
    @pytest.mark.asyncio
    async def test_non_travel_type_returns_none(self):
        db = _mock_db()
        user = _user(roles=[_std(UNIT_IID)])
        result = await crm._get_professional_travel_institutional_id_filter(
            db=db,
            unit_id=1,
            current_user=user,
            data_entry_type_id=DataEntryTypeEnum.scientific,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_plane_principal_returns_none(self):
        db = _mock_db()
        unit = MagicMock()
        unit.institutional_id = UNIT_IID
        db.get = AsyncMock(return_value=unit)
        user = _user(roles=[_principal(UNIT_IID)])

        result = await crm._get_professional_travel_institutional_id_filter(
            db=db,
            unit_id=1,
            current_user=user,
            data_entry_type_id=DataEntryTypeEnum.plane,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_plane_std_returns_institutional_id(self):
        db = _mock_db()
        unit = MagicMock()
        unit.institutional_id = UNIT_IID
        db.get = AsyncMock(return_value=unit)
        user = _user("MY_IID", roles=[_std(UNIT_IID)])

        result = await crm._get_professional_travel_institutional_id_filter(
            db=db,
            unit_id=1,
            current_user=user,
            data_entry_type_id=DataEntryTypeEnum.plane,
        )
        assert result == "MY_IID"

    @pytest.mark.asyncio
    async def test_train_std_no_institutional_id_raises(self):
        db = _mock_db()
        unit = MagicMock()
        unit.institutional_id = UNIT_IID
        db.get = AsyncMock(return_value=unit)
        user = _user(institutional_id=None, roles=[_std(UNIT_IID)])
        user.institutional_id = None

        with pytest.raises(HTTPException) as exc:
            await crm._get_professional_travel_institutional_id_filter(
                db=db,
                unit_id=1,
                current_user=user,
                data_entry_type_id=DataEntryTypeEnum.train,
            )
        assert exc.value.status_code == 403


# ── _MODULE_TOP_CLASS config dicts ────────────────────────────────────────────


def test_module_top_class_group_field_mapping():
    assert ModuleTypeEnum.equipment in crm._MODULE_TOP_CLASS_GROUP_FIELD
    assert ModuleTypeEnum.purchase in crm._MODULE_TOP_CLASS_GROUP_FIELD


# ── get_module: headline figures read off the persisted stats (#2706) ───────


def _get_module_patches(module_stats, *, hide_for_viewer=False):
    """Route collaborators for get_module with a module carrying ``stats``."""
    report, module = _resolved(module_id=99)
    module.stats = module_stats
    unit = MagicMock()
    unit.institutional_id = UNIT_IID
    data_svc = MagicMock()
    data_svc.get_module_data = AsyncMock(return_value=MagicMock())
    return (
        patch.object(
            crm, "check_module_permission_for_report", AsyncMock(return_value=unit)
        ),
        patch.object(
            crm, "resolve_report_module", AsyncMock(return_value=(report, module))
        ),
        patch.object(
            crm, "_hide_planner_snapshots_for_viewer", return_value=hide_for_viewer
        ),
        patch.object(crm, "DataEntryService", return_value=data_svc),
    )


async def _get_module(module_id: str, module_stats, *, hide_for_viewer=False):
    p1, p2, p3, p4 = _get_module_patches(module_stats, hide_for_viewer=hide_for_viewer)
    with p1, p2, p3, p4:
        return await crm.get_module(
            carbon_report_id=1,
            module_id=module_id,
            preview_limit=20,
            db=_mock_db(UNIT_IID),
            current_user=_user(roles=[_principal(UNIT_IID)]),
        )


@pytest.mark.asyncio
async def test_get_module_headcount_reads_fte_from_persisted_stats():
    """Headcount: total FTE and the chart maps come from the stats JSON, no
    per-request aggregate (#2706). Also pins the old NameError regression:
    total_kg_co2eq stays None on the headcount path.
    """
    stats = {
        "total_fte": 10.0,
        "student_fte": 4.0,
        "member_fte_by_sius_code": {"10208": 5.0},
    }
    result = await _get_module("headcount", stats)

    assert result.totals.total_kg_co2eq is None
    assert result.totals.total_annual_fte == 10.0
    assert result.stats == stats


@pytest.mark.asyncio
async def test_get_module_reads_headline_total_from_persisted_stats():
    """The sidebar total is ``total_excluding_additional``, not the every-bucket
    ``total`` — no live get_stats aggregate anymore (#2706).
    """
    stats = {
        "total": 41_000.0,
        "total_excluding_additional": 6_000.0,
        "planner_snapshot_kg": 500.0,
    }
    result = await _get_module("buildings", stats)

    assert result.totals.total_kg_co2eq == 6_000.0
    assert result.totals.total_tonnes_co2eq == 6.0
    assert result.totals.total_annual_fte is None
    assert result.stats is stats


@pytest.mark.asyncio
async def test_get_module_hides_planner_snapshot_kg_from_restricted_viewer():
    """A viewer who may not see the reference-year prefill rows (#1983) must not
    see their kg in the headline either: the persisted split is subtracted.
    """
    stats = {"total_excluding_additional": 6_000.0, "planner_snapshot_kg": 500.0}
    result = await _get_module("buildings", stats, hide_for_viewer=True)

    assert result.totals.total_kg_co2eq == 5_500.0


@pytest.mark.asyncio
async def test_get_module_without_stats_has_no_totals():
    """A module never recomputed (no entries yet) reports no headline, not 0."""
    result = await _get_module("buildings", None)

    assert result.totals.total_kg_co2eq is None
    assert result.totals.total_tonnes_co2eq is None


@pytest.mark.asyncio
async def test_get_module_fails_loud_when_stats_predate_2706():
    """Stats written before #2706 lack the headline keys: a 503 pointing at the
    admin recompute-stats trigger, never a silent zero.
    """
    with pytest.raises(HTTPException) as exc:
        await _get_module("buildings", {"total": 41_000.0})

    assert exc.value.status_code == 503
    assert "recompute-stats" in exc.value.detail


# ======================================================================
# #2050 J4 — WriteScope threads resolved identity through the write
# ======================================================================


@pytest.mark.asyncio
async def test_write_scope_carries_year_and_unit_from_the_report():
    """WriteScope is the carrier that stops four services re-reading the
    report, project and module the route already resolved.
    """
    report = MagicMock()
    report.year = 2025
    report.unit_id = 7
    module = MagicMock()
    module.id = 42

    scope = crm.WriteScope.model_construct(
        report=report, module=module, is_simulator=False
    )

    assert scope.year == 2025
    assert scope.unit_id == 7
    assert scope.module.id == 42
    assert scope.is_simulator is False
