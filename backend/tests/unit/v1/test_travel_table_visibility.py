"""Unit tests for travel table institutional_id filtering logic.

Tests the two functions that control whether a user sees all travel entries
or only their own:

- _has_global_or_principal_access_for_unit (sync)
- _get_professional_travel_institutional_id_filter (async)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.carbon_report_module import (
    _get_professional_travel_institutional_id_filter,
    _has_global_or_principal_access_for_unit,
)
from app.models.data_entry import DataEntryTypeEnum
from app.models.user import GlobalScope, Role, RoleName, RoleScope

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
        role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(institutional_id=unit_iid)
    )


def _std_role(unit_iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id=unit_iid))


def _global_role() -> Role:
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _make_db(unit):
    db = MagicMock()
    db.get = AsyncMock(return_value=unit)
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
        unit_id=1,
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
        db=db, unit_id=1, current_user=user, data_entry_type_id=DataEntryTypeEnum.plane
    )
    assert result is None


@pytest.mark.asyncio
async def test_global_role_gets_no_filter():
    user = _make_user(USER_IID, [_global_role()])
    db = _make_db(_make_unit(UNIT_IID))
    result = await _get_professional_travel_institutional_id_filter(
        db=db, unit_id=1, current_user=user, data_entry_type_id=DataEntryTypeEnum.train
    )
    assert result is None


@pytest.mark.asyncio
async def test_std_user_gets_own_iid_as_filter():
    user = _make_user(USER_IID, [_std_role(UNIT_IID)])
    db = _make_db(_make_unit(UNIT_IID))
    result = await _get_professional_travel_institutional_id_filter(
        db=db, unit_id=1, current_user=user, data_entry_type_id=DataEntryTypeEnum.plane
    )
    assert result == USER_IID


@pytest.mark.asyncio
async def test_std_user_without_iid_raises_403():
    user = _make_user(None, [_std_role(UNIT_IID)])
    db = _make_db(_make_unit(UNIT_IID))
    with pytest.raises(HTTPException) as exc_info:
        await _get_professional_travel_institutional_id_filter(
            db=db,
            unit_id=1,
            current_user=user,
            data_entry_type_id=DataEntryTypeEnum.plane,
        )
    assert exc_info.value.status_code == 403
