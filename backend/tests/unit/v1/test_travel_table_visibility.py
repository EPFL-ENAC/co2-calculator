"""Unit tests for travel table institutional_id filtering logic.

Tests the functions that control whether a user sees all travel entries
or only their own:

- _has_global_or_principal_access_for_unit (sync)
- _get_professional_travel_institutional_id_filter (async)
- _is_explore_report (async) — the Explore exemption (#2752)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.carbon_report_module import (
    _get_professional_travel_institutional_id_filter,
    _has_global_or_principal_access_for_unit,
    _is_explore_report,
)
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportType
from app.models.data_entry import DataEntryTypeEnum
from app.models.user import GlobalScope, OwnScope, Role, RoleName, UnitScope

UNIT_IID = "10208"
OTHER_UNIT_IID = "99999"
USER_IID = "11111"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(institutional_id, roles):
    user = MagicMock()
    user.institutional_id = institutional_id
    user.roles = roles
    return user


def _make_unit(institutional_id):
    unit = MagicMock()
    unit.institutional_id = institutional_id
    return unit


def _principal_role(unit_iid: str) -> Role:
    return Role(
        role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id=unit_iid)
    )


def _std_role(unit_iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id=unit_iid))


def _global_role() -> Role:
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _make_report(carbon_project_id=None):
    report = MagicMock()
    report.unit_id = 1
    report.carbon_project_id = carbon_project_id
    return report


def _make_project(carbon_report_type):
    project = MagicMock()
    project.carbon_report_type = carbon_report_type
    return project


def _make_db(unit, project=None):
    """``db.get`` keyed on model: the unit for Unit, ``project`` for CarbonProject."""
    db = MagicMock()

    async def _get(model, _pk):
        if model is CarbonProject:
            return project
        return unit

    db.get = AsyncMock(side_effect=_get)
    return db


# ── _has_global_or_principal_access_for_unit ─────────────────────────────────


def test_global_role_grants_full_access():
    user = _make_user(USER_IID, [_global_role()])
    assert _has_global_or_principal_access_for_unit(user, _make_unit(UNIT_IID)) is True


def test_principal_for_this_unit_grants_full_access():
    user = _make_user(USER_IID, [_principal_role(UNIT_IID)])
    assert _has_global_or_principal_access_for_unit(user, _make_unit(UNIT_IID)) is True


def test_std_for_this_unit_denied_full_access():
    user = _make_user(USER_IID, [_std_role(UNIT_IID)])
    assert _has_global_or_principal_access_for_unit(user, _make_unit(UNIT_IID)) is False


def test_principal_for_other_unit_denied_full_access():
    user = _make_user(USER_IID, [_principal_role(OTHER_UNIT_IID)])
    assert _has_global_or_principal_access_for_unit(user, _make_unit(UNIT_IID)) is False


def test_unit_without_institutional_code_denied_full_access():
    """If the unit has no institutional_code the role check cannot be done."""
    user = _make_user(USER_IID, [_principal_role(UNIT_IID)])
    assert _has_global_or_principal_access_for_unit(user, _make_unit(None)) is False


def test_none_unit_denied_full_access():
    user = _make_user(USER_IID, [_principal_role(UNIT_IID)])
    assert _has_global_or_principal_access_for_unit(user, None) is False


def test_principal_plus_std_for_other_unit_denied_full_access():
    """Principal of unit A + STD for unit B accessing unit B → denied."""
    user = _make_user(USER_IID, [_principal_role(OTHER_UNIT_IID), _std_role(UNIT_IID)])
    assert _has_global_or_principal_access_for_unit(user, _make_unit(UNIT_IID)) is False


# ── _get_professional_travel_institutional_id_filter ─────────────────────────


@pytest.mark.asyncio
async def test_non_travel_type_returns_none():
    """Non-travel data_entry_type is never filtered regardless of role."""
    user = _make_user(USER_IID, [_std_role(UNIT_IID)])
    db = _make_db(_make_unit(UNIT_IID))
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.member,
    )
    assert result is None
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_principal_gets_no_filter():
    user = _make_user(USER_IID, [_principal_role(UNIT_IID)])
    db = _make_db(_make_unit(UNIT_IID))
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.plane,
    )
    assert result is None


@pytest.mark.asyncio
async def test_global_role_gets_no_filter():
    user = _make_user(USER_IID, [_global_role()])
    db = _make_db(_make_unit(UNIT_IID))
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.train,
    )
    assert result is None


@pytest.mark.asyncio
async def test_std_user_gets_own_iid_as_filter():
    user = _make_user(USER_IID, [_std_role(UNIT_IID)])
    db = _make_db(_make_unit(UNIT_IID))
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.plane,
    )
    assert result == USER_IID


@pytest.mark.asyncio
async def test_std_user_without_iid_raises_403():
    user = _make_user(None, [_std_role(UNIT_IID)])
    db = _make_db(_make_unit(UNIT_IID))
    with pytest.raises(HTTPException) as exc_info:
        await _get_professional_travel_institutional_id_filter(
            db=db,
            report=_make_report(),
            current_user=user,
            data_entry_type_id=DataEntryTypeEnum.plane,
        )
    assert exc_info.value.status_code == 403


# ── Explore sandbox exemption (#2752) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_std_user_in_explore_sandbox_gets_no_filter():
    """Regression for #2752: an Explore sandbox is private to its creator, so
    the own-rows filter must not apply — it hid the sentinel-traveler trips a
    standard user had just added.
    """
    user = _make_user(USER_IID, [_std_role(UNIT_IID)])
    db = _make_db(
        _make_unit(UNIT_IID),
        project=_make_project(CarbonReportType.SIMULATOR_EXPLORE),
    )
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(carbon_project_id=5),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.plane,
    )
    assert result is None


@pytest.mark.asyncio
async def test_std_user_without_iid_in_explore_sandbox_is_not_rejected():
    """The 403 for a missing institutional id guards the shared Calculator
    data; the caller's own sandbox never needs that scope.
    """
    user = _make_user(None, [_std_role(UNIT_IID)])
    db = _make_db(
        _make_unit(UNIT_IID),
        project=_make_project(CarbonReportType.SIMULATOR_EXPLORE),
    )
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(carbon_project_id=5),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.train,
    )
    assert result is None


@pytest.mark.asyncio
async def test_std_user_in_plan_report_keeps_own_filter():
    """Plans are shared across the unit — the own-rows filter still applies."""
    user = _make_user(USER_IID, [_std_role(UNIT_IID)])
    db = _make_db(
        _make_unit(UNIT_IID),
        project=_make_project(CarbonReportType.SIMULATOR_PLAN),
    )
    result = await _get_professional_travel_institutional_id_filter(
        db=db,
        report=_make_report(carbon_project_id=5),
        current_user=user,
        data_entry_type_id=DataEntryTypeEnum.plane,
    )
    assert result == USER_IID


@pytest.mark.asyncio
async def test_is_explore_report_without_project_is_false():
    db = _make_db(_make_unit(UNIT_IID))
    assert await _is_explore_report(db, _make_report()) is False
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_is_explore_report_true_only_for_explore_projects():
    explore_db = _make_db(
        None, project=_make_project(CarbonReportType.SIMULATOR_EXPLORE)
    )
    calc_db = _make_db(None, project=_make_project(CarbonReportType.CALCULATOR))
    report = _make_report(carbon_project_id=5)
    assert await _is_explore_report(explore_db, report) is True
    assert await _is_explore_report(calc_db, report) is False
