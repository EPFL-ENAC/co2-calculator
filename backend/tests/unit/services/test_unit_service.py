"""Unit tests for unit service."""

from app.models.unit import Unit
from app.models.user import GlobalScope, Role, RoleName, User
from app.services.unit_service import UnitService


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
            created_by="creator-id",
            visibility="private",
        )

        service = UnitService(session=None)
        input_data = service._build_policy_input(user, "update", unit)

        assert input_data["action"] == "update"
        assert input_data["resource_type"] == "unit"
        assert "resource" in input_data
        assert input_data["resource"]["id"] == "test-unit"
        assert input_data["resource"]["created_by"] == "creator-id"
        assert input_data["resource"]["visibility"] == "private"

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
