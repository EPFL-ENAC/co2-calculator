"""Unit tests for authorization_service - policy-based authorization helpers."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.authorization_service import (
    _build_data_filter_input,
    _build_resource_access_input,
    check_resource_access,
    get_data_filters,
)


class TestBuildDataFilterInput:
    """Tests for _build_data_filter_input helper function."""

    def test_build_data_filter_input_with_roles(self):
        """Test building data filter input with user that has roles."""
        # Create mock user
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["unit_manager", "standard_user"]

        result = _build_data_filter_input(user, "headcount", "list")

        assert result == {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "roles": ["unit_manager", "standard_user"],
            },
            "resource_type": "headcount",
            "action": "list",
        }

    def test_build_data_filter_input_without_roles(self):
        """Test building data filter input with user that has no roles."""
        user = MagicMock()
        user.id = "user-456"
        user.email = "noroles@example.com"
        user.roles = []

        result = _build_data_filter_input(user, "equipment", "read")

        assert result == {
            "user": {
                "id": "user-456",
                "email": "noroles@example.com",
                "roles": [],
            },
            "resource_type": "equipment",
            "action": "read",
        }

    def test_build_data_filter_input_with_none_roles(self):
        """Test building data filter input with user that has None for roles."""
        user = MagicMock()
        user.id = "user-789"
        user.email = "none@example.com"
        user.roles = None

        result = _build_data_filter_input(user, "professional_travel", "list")

        # Should handle None roles by converting to empty list in output
        assert result == {
            "user": {
                "id": "user-789",
                "email": "none@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
            "action": "list",
        }

    def test_build_data_filter_input_different_resource_types(self):
        """Test building data filter input with various resource types."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        # Test different resource types
        for resource_type in [
            "headcount",
            "equipment",
            "professional_travel",
            "external_clouds",
        ]:
            result = _build_data_filter_input(user, resource_type, "list")
            assert result["resource_type"] == resource_type

    def test_build_data_filter_input_different_actions(self):
        """Test building data filter input with various actions."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        # Test different actions
        for action in ["list", "read", "access", "create", "update", "delete"]:
            result = _build_data_filter_input(user, "headcount", action)
            assert result["action"] == action


class TestBuildResourceAccessInput:
    """Tests for _build_resource_access_input helper function."""

    def test_build_resource_access_input_standard_resource(self):
        """Test building resource access input with standard resource."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["standard_user"]

        resource = {"id": 456, "created_by": "user-123", "unit_id": "12345"}

        result = _build_resource_access_input(user, "headcount", resource)

        assert result == {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "roles": ["standard_user"],
            },
            "resource_type": "headcount",
            "action": "access",
            "resource": {"id": 456, "created_by": "user-123", "unit_id": "12345"},
        }

    def test_build_resource_access_input_with_provider(self):
        """Test building resource access input with provider field."""
        user = MagicMock()
        user.id = "user-789"
        user.email = "test@example.com"
        user.roles = ["unit_manager"]

        resource = {
            "id": 789,
            "created_by": "user-456",
            "unit_id": "67890",
            "provider": "api",
        }

        result = _build_resource_access_input(user, "professional_travel", resource)

        assert result["resource"]["provider"] == "api"
        assert result["resource"]["id"] == 789

    def test_build_resource_access_input_without_roles(self):
        """Test building resource access input with user that has no roles."""
        user = MagicMock()
        user.id = "user-no-roles"
        user.email = "noroles@example.com"
        user.roles = []

        resource = {"id": 100, "created_by": "user-no-roles"}

        result = _build_resource_access_input(user, "equipment", resource)

        assert result["user"]["roles"] == []

    def test_build_resource_access_input_with_none_roles(self):
        """Test building resource access input with None roles."""
        user = MagicMock()
        user.id = "user-none"
        user.email = "none@example.com"
        user.roles = None

        resource = {"id": 200, "created_by": "user-none"}

        result = _build_resource_access_input(user, "equipment", resource)

        assert result["user"]["roles"] == []

    def test_build_resource_access_input_action_always_access(self):
        """Test that action is always set to 'access' in resource access input."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        resource = {"id": 300}

        result = _build_resource_access_input(user, "headcount", resource)

        assert result["action"] == "access"


class TestGetDataFilters:
    """Tests for get_data_filters async function."""

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_allow_with_filters(self, mock_query_policy):
        """Test get_data_filters when policy allows with filters."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["unit_manager"]

        # Mock policy decision
        mock_query_policy.return_value = {
            "allow": True,
            "filters": {
                "unit_ids": ["12345", "67890"],
                "scope": "unit",
            },
        }

        result = await get_data_filters(user, "headcount", "list")

        # Verify query_policy was called correctly
        mock_query_policy.assert_called_once()
        call_args = mock_query_policy.call_args
        assert call_args[0][0] == "authz/data/list"
        assert call_args[0][1]["user"]["id"] == "user-123"
        assert call_args[0][1]["resource_type"] == "headcount"
        assert call_args[0][1]["action"] == "list"

        # Verify filters returned
        assert result == {"unit_ids": ["12345", "67890"], "scope": "unit"}

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_allow_global_scope(self, mock_query_policy):
        """Test get_data_filters for admin with global scope."""
        user = MagicMock()
        user.id = "admin-user"
        user.email = "admin@example.com"
        user.roles = ["admin"]

        mock_query_policy.return_value = {
            "allow": True,
            "filters": {"scope": "global"},
        }

        result = await get_data_filters(user, "equipment", "list")

        assert result == {"scope": "global"}

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_deny_access(self, mock_query_policy):
        """Test get_data_filters when policy denies access."""
        user = MagicMock()
        user.id = "user-denied"
        user.email = "denied@example.com"
        user.roles = []

        # Policy denies access
        mock_query_policy.return_value = {
            "allow": False,
            "reason": "Insufficient permissions",
        }

        result = await get_data_filters(user, "headcount", "list")

        # Should return restrictive filters
        assert result == {"user_id": "user-denied", "scope": "denied"}

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_own_scope(self, mock_query_policy):
        """Test get_data_filters for standard user with own scope."""
        user = MagicMock()
        user.id = "standard-user"
        user.email = "standard@example.com"
        user.roles = ["standard_user"]

        mock_query_policy.return_value = {
            "allow": True,
            "filters": {"user_id": "standard-user", "scope": "own"},
        }

        result = await get_data_filters(user, "professional_travel", "list")

        assert result == {"user_id": "standard-user", "scope": "own"}

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_default_action(self, mock_query_policy):
        """Test get_data_filters uses 'list' as default action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        mock_query_policy.return_value = {
            "allow": True,
            "filters": {"scope": "global"},
        }

        # Call without explicit action
        await get_data_filters(user, "equipment")

        # Verify default action is 'list'
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "list"

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_custom_action(self, mock_query_policy):
        """Test get_data_filters with custom action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        mock_query_policy.return_value = {
            "allow": True,
            "filters": {},
        }

        await get_data_filters(user, "equipment", "read")

        # Verify custom action is passed
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "read"

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_empty_filters(self, mock_query_policy):
        """Test get_data_filters when policy returns empty filters."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        mock_query_policy.return_value = {"allow": True, "filters": {}}

        result = await get_data_filters(user, "equipment", "list")

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_get_data_filters_no_filters_key(self, mock_query_policy):
        """Test get_data_filters when policy returns no filters key."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        # Policy returns only 'allow' without 'filters' key
        mock_query_policy.return_value = {"allow": True}

        result = await get_data_filters(user, "equipment", "list")

        # Should return empty dict when filters key is missing
        assert result == {}


class TestCheckResourceAccess:
    """Tests for check_resource_access async function."""

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_allow(self, mock_query_policy):
        """Test check_resource_access when policy allows access."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["unit_manager"]

        resource = {"id": 456, "created_by": "user-123", "unit_id": "12345"}

        # Policy allows access
        mock_query_policy.return_value = {"allow": True}

        result = await check_resource_access(user, "headcount", resource)

        # Verify query_policy was called correctly
        mock_query_policy.assert_called_once()
        call_args = mock_query_policy.call_args
        assert call_args[0][0] == "authz/resource/access"
        assert call_args[0][1]["user"]["id"] == "user-123"
        assert call_args[0][1]["resource_type"] == "headcount"
        assert call_args[0][1]["resource"]["id"] == 456

        # Should return True
        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_deny(self, mock_query_policy):
        """Test check_resource_access when policy denies access."""
        user = MagicMock()
        user.id = "user-456"
        user.email = "test@example.com"
        user.roles = ["standard_user"]

        resource = {
            "id": 789,
            "created_by": "user-123",  # Different user
            "unit_id": "12345",
        }

        # Policy denies access
        mock_query_policy.return_value = {"allow": False, "reason": "Not owner"}

        result = await check_resource_access(user, "headcount", resource)

        # Should return False
        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_with_provider(self, mock_query_policy):
        """Test check_resource_access with professional travel resource."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["unit_manager"]

        resource = {
            "id": 100,
            "created_by": "user-456",
            "unit_id": "12345",
            "provider": "api",
        }

        mock_query_policy.return_value = {"allow": False}

        result = await check_resource_access(user, "professional_travel", resource)

        # Verify resource with provider was passed correctly
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["resource"]["provider"] == "api"

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_default_action(self, mock_query_policy):
        """Test check_resource_access uses 'access' as default action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        resource = {"id": 123}

        mock_query_policy.return_value = {"allow": True}

        await check_resource_access(user, "equipment", resource)

        # Verify default action is 'access'
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "access"

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_custom_action(self, mock_query_policy):
        """Test check_resource_access with custom action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        resource = {"id": 123}

        mock_query_policy.return_value = {"allow": True}

        await check_resource_access(user, "equipment", resource, "delete")

        # Verify custom action is passed
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "delete"

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_no_allow_key(self, mock_query_policy):
        """Test check_resource_access when policy returns no 'allow' key."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        resource = {"id": 123}

        # Policy returns empty dict (no 'allow' key)
        mock_query_policy.return_value = {}

        result = await check_resource_access(user, "equipment", resource)

        # Should default to False when 'allow' is missing
        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.authorization_service.query_policy")
    async def test_check_resource_access_admin_user(self, mock_query_policy):
        """Test check_resource_access for admin user."""
        user = MagicMock()
        user.id = "admin-123"
        user.email = "admin@example.com"
        user.roles = ["admin"]

        resource = {"id": 999, "created_by": "other-user", "unit_id": "99999"}

        mock_query_policy.return_value = {"allow": True}

        result = await check_resource_access(user, "headcount", resource)

        assert result is True
