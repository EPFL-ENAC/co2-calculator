"""Unit tests for carbon_report_module endpoint helpers and list_headcount_members.

Covers:
- get_carbon_report / get_carbon_report_id helpers
- list_headcount_members: permission gate, data-level scope, role-priority fix
- pick_role_for_institutional_id (role_priority module)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.carbon_report_module as crm
from app.core.role_priority import pick_role_for_institutional_id, role_priority_case
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import GlobalScope, Role, RoleName, RoleScope

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
        role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(institutional_id=unit_iid)
    )


def _std(unit_iid=UNIT_IID):
    return Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id=unit_iid))


def _global():
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _mock_db(unit_iid=UNIT_IID, unit_found=True):
    db = MagicMock()
    unit = MagicMock()
    unit.institutional_id = unit_iid
    db.get = AsyncMock(return_value=unit if unit_found else None)
    return db


# ── get_carbon_report ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_carbon_report_returns_module():
    db = MagicMock()
    mock_module = MagicMock()
    mock_module.id = 42
    service = MagicMock()
    service.get_carbon_report_by_year_and_unit = AsyncMock(return_value=mock_module)

    with patch.object(crm, "CarbonReportModuleService", return_value=service):
        result = await crm.get_carbon_report(1, 2024, ModuleTypeEnum.headcount, db)

    assert result.id == 42


@pytest.mark.asyncio
async def test_get_carbon_report_raises_404_when_not_found():
    db = MagicMock()
    service = MagicMock()
    service.get_carbon_report_by_year_and_unit = AsyncMock(return_value=None)

    with patch.object(crm, "CarbonReportModuleService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await crm.get_carbon_report(1, 2024, ModuleTypeEnum.headcount, db)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_carbon_report_raises_404_when_id_is_none():
    db = MagicMock()
    mock_module = MagicMock()
    mock_module.id = None
    service = MagicMock()
    service.get_carbon_report_by_year_and_unit = AsyncMock(return_value=mock_module)

    with patch.object(crm, "CarbonReportModuleService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await crm.get_carbon_report(1, 2024, ModuleTypeEnum.headcount, db)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_carbon_report_id_returns_int():
    db = MagicMock()
    mock_module = MagicMock()
    mock_module.id = 7
    service = MagicMock()
    service.get_carbon_report_by_year_and_unit = AsyncMock(return_value=mock_module)

    with patch.object(crm, "CarbonReportModuleService", return_value=service):
        result = await crm.get_carbon_report_id(1, 2024, ModuleTypeEnum.headcount, db)

    assert result == 7


# ── list_headcount_members: permission gate ───────────────────────────────────


@pytest.mark.asyncio
async def test_list_headcount_members_403_when_no_permission():
    user = _user(roles=[])
    db = _mock_db()

    async def deny_all(u, mod, action):
        return {"allow": False}

    with patch.object(crm, "get_module_permission_decision", side_effect=deny_all):
        with pytest.raises(HTTPException) as exc:
            await crm.list_headcount_members(1, 2024, db, user)

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

    async def allow_headcount(u, mod, action):
        return {"allow": mod == "headcount"}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)

    with (
        patch.object(
            crm, "get_module_permission_decision", side_effect=allow_headcount
        ),
        patch.object(crm, "get_carbon_report_id", AsyncMock(return_value=1)),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, 2024, db, user)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_headcount_members_global_role_sees_all():
    user = _user("11111", [_global()])
    db = _mock_db(UNIT_IID)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_all(u, mod, action):
        return {"allow": True}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)

    with (
        patch.object(crm, "get_module_permission_decision", side_effect=allow_all),
        patch.object(crm, "get_carbon_report_id", AsyncMock(return_value=1)),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, 2024, db, user)

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

    async def allow_travel(u, mod, action):
        return {"allow": mod == "professional-travel"}

    svc = MagicMock()
    svc.get_headcount_members = AsyncMock(return_value=members)
    svc.get_member_by_institutional_id = AsyncMock(
        return_value={"institutional_id": "11111", "name": "A"}
    )

    with (
        patch.object(crm, "get_module_permission_decision", side_effect=allow_travel),
        patch.object(crm, "get_carbon_report_id", AsyncMock(return_value=1)),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, 2024, db, user)

    assert len(result) == 1
    assert result[0].institutional_id == "11111"


@pytest.mark.asyncio
async def test_list_headcount_members_principal_other_unit_sees_only_own():
    """Principal of unit B accessing unit A sees only their own record
    (role priority)."""
    user = _user("11111", [_principal("99999"), _std(UNIT_IID)])
    db = _mock_db(UNIT_IID)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_headcount(u, mod, action):
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
        patch.object(crm, "get_carbon_report_id", AsyncMock(return_value=1)),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, 2024, db, user)

    assert len(result) == 1
    assert result[0].institutional_id == "11111"


@pytest.mark.asyncio
async def test_list_headcount_members_unit_not_found_restricts_access():
    """When unit row is missing from DB, has_full_access falls back to False."""
    user = _user("11111", [_principal(UNIT_IID)])
    db = _mock_db(unit_found=False)
    members = [
        {"institutional_id": "11111", "name": "A"},
        {"institutional_id": "22222", "name": "B"},
    ]

    async def allow_headcount(u, mod, action):
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
        patch.object(crm, "get_carbon_report_id", AsyncMock(return_value=1)),
        patch.object(crm, "DataEntryService", return_value=svc),
    ):
        result = await crm.list_headcount_members(1, 2024, db, user)

    # unit_iid is None → pick_role_for_institutional_id not called
    # → has_full_access=False
    assert len(result) == 1
    assert result[0].institutional_id == "11111"


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
    assert (
        ModuleTypeEnum.equipment_electric_consumption
        in crm._MODULE_TOP_CLASS_GROUP_FIELD
    )
    assert ModuleTypeEnum.purchase in crm._MODULE_TOP_CLASS_GROUP_FIELD


def test_module_top_class_label_field_mapping():
    assert ModuleTypeEnum.purchase in crm._MODULE_TOP_CLASS_LABEL_FIELD
