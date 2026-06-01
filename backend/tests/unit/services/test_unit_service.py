"""Unit tests for unit service."""

import pytest

from app.models.unit import Unit
from app.models.user import GlobalScope, Role, RoleName, User
from app.services.unit_service import UnitService


@pytest.fixture
def mock_unit_service_policy_allow(monkeypatch):
    """Patch query_policy as imported by unit_service (no filters, allow)."""

    async def _mock(*args, **kwargs):
        return {"allow": True, "filters": {}}

    monkeypatch.setattr("app.services.unit_service.query_policy", _mock)
    return _mock


class TestGetUserUnitsLevelFilter:
    """Regression tests for #930 — /users/units must return only level-4 units."""

    async def test_get_user_units_returns_only_level_4_when_user_has_mixed_level_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        """User holding roles across levels 2, 3, 4 sees only the level-4 unit."""
        user = await make_user(db_session)
        unit_l2 = await make_unit(db_session, level=2, name="Faculty")
        unit_l3 = await make_unit(db_session, level=3, name="Institute")
        unit_l4 = await make_unit(db_session, level=4, name="Lab")
        for unit in (unit_l2, unit_l3, unit_l4):
            await make_unit_user(
                db_session,
                unit_id=unit.id,
                user_id=user.id,
                role=RoleName.CO2_USER_PRINCIPAL,
            )

        service = UnitService(session=db_session)
        result = await service.get_user_units(user)

        assert [row["name"] for row in result] == ["Lab"]

    async def test_get_user_units_returns_empty_when_user_only_has_non_level_4_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        """User with only level-3 roles → empty list (filter excludes everything)."""
        user = await make_user(db_session)
        unit_l3 = await make_unit(db_session, level=3, name="Institute")
        await make_unit_user(
            db_session,
            unit_id=unit_l3.id,
            user_id=user.id,
            role=RoleName.CO2_USER_PRINCIPAL,
        )

        service = UnitService(session=db_session)
        result = await service.get_user_units(user)

        assert result == []

    async def test_get_user_units_unchanged_for_user_with_only_level_4_roles(
        self,
        db_session,
        make_unit,
        make_user,
        make_unit_user,
        mock_unit_service_policy_allow,
    ):
        """Baseline: level-4-only users see all their labs (no regression)."""
        user = await make_user(db_session)
        lab_a = await make_unit(db_session, level=4, name="LabA")
        lab_b = await make_unit(db_session, level=4, name="LabB")
        for lab in (lab_a, lab_b):
            await make_unit_user(
                db_session,
                unit_id=lab.id,
                user_id=user.id,
                role=RoleName.CO2_USER_PRINCIPAL,
            )

        service = UnitService(session=db_session)
        result = await service.get_user_units(user)

        assert sorted(row["name"] for row in result) == ["LabA", "LabB"]


class TestBuildPolicyInput:
    """Tests for _build_policy_input method."""

    def test_build_policy_input_without_unit(self):
        """Test building policy input without unit context."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]

        service = UnitService(session=None)
        input_data = service._build_policy_input(user, "read")

        assert input_data["action"] == "read"
        assert input_data["resource_type"] == "unit"
        assert input_data["user"]["id"] == "test-user"
        assert input_data["user"]["email"] == "test@example.com"
        assert len(input_data["user"]["roles"]) == 1
        assert "resource" not in input_data

    def test_build_policy_input_with_unit(self):
        """Test building policy input with unit context."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]

        unit = Unit(
            id="test-unit",
            name="Test Unit",
        )

        service = UnitService(session=None)
        input_data = service._build_policy_input(user, "update", unit)

        assert input_data["action"] == "update"
        assert input_data["resource_type"] == "unit"
        assert "resource" in input_data
        assert input_data["resource"]["id"] == "test-unit"

    def test_build_policy_input_different_actions(self):
        """Test building policy input for different actions."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )

        service = UnitService(session=None)

        for action in ["read", "create", "update", "delete"]:
            input_data = service._build_policy_input(user, action)
            assert input_data["action"] == action

    def test_build_policy_input_user_without_roles(self):
        """Test building policy input for user without roles."""
        user = User(
            id="test-user",
            email="test@example.com",
            display_name="Test User",
            provider="test",
        )
        user.roles = []

        service = UnitService(session=None)
        input_data = service._build_policy_input(user, "read")

        assert input_data["user"]["roles"] == []
