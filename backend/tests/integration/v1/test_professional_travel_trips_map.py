"""Integration tests for /professional-travel/trips-map (issue #282).

Mirrors test_headcount_members_permission.py — we mock the service layer
and exercise the permission gate + own-scope institutional_id filter.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps_module
from app.main import app
from app.models.user import (
    AffiliationScope,
    GlobalScope,
    OwnScope,
    Role,
    RoleName,
    UnitScope,
)
from app.schemas.carbon_report_response import TripsMapResponse


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


UNIT_IID = "10208"
URL = "/api/v1/modules/1/2024/professional-travel/trips-map"

ALL_LEGS = [
    {
        "mode": "plane",
        "origin_lat": 46.2381,
        "origin_lng": 6.1090,
        "destination_lat": 40.6413,
        "destination_lng": -73.7781,
        "origin_name": "Geneva Airport",
        "destination_name": "JFK",
        "kg_co2eq": 1234.5,
    },
    {
        "mode": "train",
        "origin_lat": 46.5167,
        "origin_lng": 6.6333,
        "destination_lat": 48.8566,
        "destination_lng": 2.3522,
        "origin_name": "Lausanne",
        "destination_name": "Paris",
        "kg_co2eq": 10.0,
    },
]


def _make_user(institutional_id: str, roles: list) -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    user.institutional_id = institutional_id
    user.roles = roles
    return user


def _principal_role(unit_iid: str) -> Role:
    return Role(
        role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id=unit_iid)
    )


def _std_role(unit_iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id=unit_iid))


def _metier_role(affiliation: str) -> Role:
    return Role(
        role=RoleName.CO2_BACKOFFICE_METIER,
        on=AffiliationScope(affiliation=affiliation),
    )


def _global_role() -> Role:
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


def _wire(monkeypatch, user, decision_fn):
    app.dependency_overrides[deps_module.get_current_user] = lambda: user
    monkeypatch.setattr(
        "app.core.policy.get_module_permission_decision",
        decision_fn,
    )
    mock_unit = MagicMock()
    mock_unit.institutional_id = UNIT_IID
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.get_carbon_report_id",
        AsyncMock(return_value=1),
    )

    captured: dict = {}
    mock_service = MagicMock()

    async def mock_trips_map(carbon_report_module_id, institutional_id_filter=None):
        captured["filter"] = institutional_id_filter
        legs = ALL_LEGS
        if institutional_id_filter is not None:
            # Toy filter: keep only the train leg when scoped to user 11111.
            legs = [ALL_LEGS[1]]
        return TripsMapResponse.model_validate({"legs": legs, "dropped_count": 0})

    mock_service.get_professional_travel_trips_map = mock_trips_map
    monkeypatch.setattr(
        "app.api.v1.carbon_report_module.DataEntryService", lambda db: mock_service
    )

    async def mock_get_db():
        db = MagicMock()
        db.get = AsyncMock(return_value=mock_unit)
        yield db

    app.dependency_overrides[deps_module.get_db] = mock_get_db
    return captured


async def _allow_travel_only(user, module_id, action, **_kwargs):
    return {"allow": module_id == "professional-travel"}


async def _allow_all(user, module_id, action, **_kwargs):
    return {"allow": True}


async def _deny_all(user, module_id, action, **_kwargs):
    return {"allow": False}


def test_403_when_no_permission_metier(client, monkeypatch):
    user = _make_user("11111", [_metier_role("SV_TEST")])
    _wire(monkeypatch, user, _deny_all)
    try:
        r = client.get(URL)
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_200_when_standard(client, monkeypatch):
    user = _make_user("11111", [_std_role(UNIT_IID)])
    _wire(monkeypatch, user, _allow_all)
    try:
        r = client.get(URL)
        assert r.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_principal_sees_full_unit_data(client, monkeypatch):
    user = _make_user("11111", [_principal_role(UNIT_IID)])
    captured = _wire(monkeypatch, user, _allow_all)
    try:
        r = client.get(URL)
        assert r.status_code == 200
        assert captured["filter"] is None
        legs = r.json()["legs"]
        assert len(legs) == 2
    finally:
        app.dependency_overrides.clear()


def test_global_don_t_sees_full_unit_data(client, monkeypatch):
    user = _make_user("99999", [_global_role()])
    _wire(monkeypatch, user, _deny_all)
    try:
        r = client.get(URL)
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_std_user_scoped_to_own_institutional_id(client, monkeypatch):
    user = _make_user("11111", [_std_role(UNIT_IID)])
    captured = _wire(monkeypatch, user, _allow_travel_only)
    try:
        r = client.get(URL)
        assert r.status_code == 200
        assert captured["filter"] == "11111"
        legs = r.json()["legs"]
        assert len(legs) == 1
        assert legs[0]["mode"] == "train"
    finally:
        app.dependency_overrides.clear()
