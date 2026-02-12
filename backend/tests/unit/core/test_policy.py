"""Unit tests for core policy module - authorization policy evaluation."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.policy import (
    _get_module_permission_path,
    check_module_permission,
    query_policy,
)
from app.models.user import Role, RoleName, RoleScope


class TestGetModulePermissionPath:
    """Tests for _get_module_permission_path function."""

    def test_professional_travel_module(self):
        """Test mapping for professional-travel module."""
        result = _get_module_permission_path("professional-travel")
        assert result == "modules.professional_travel"

    def test_equipment_module(self):
        """Test mapping for equipment-electric-consumption module."""
        result = _get_module_permission_path("equipment-electric-consumption")
        assert result == "modules.equipment"

    def test_infrastructure_module(self):
        """Test mapping for infrastructure module."""
        result = _get_module_permission_path("infrastructure")
        assert result == "modules.infrastructure"

    def test_purchase_module(self):
        """Test mapping for purchase module."""
        result = _get_module_permission_path("purchase")
        assert result == "modules.purchase"

    def test_internal_services_module(self):
        """Test mapping for internal-services module."""
        result = _get_module_permission_path("internal-services")
        assert result == "modules.internal_services"

    def test_external_cloud_and_ai_module(self):
        """Test mapping for external-cloud-and-ai module."""
        result = _get_module_permission_path("external-cloud-and-ai")
        assert result == "modules.external_cloud_and_ai"

    def test_my_lab_module(self):
        """Test mapping for my-lab module (headcount)."""
        result = _get_module_permission_path("my-lab")
        assert result == "modules.headcount"

    def test_unknown_module_returns_none(self):
        """Test that unknown module ID returns None."""
        result = _get_module_permission_path("unknown-module")
        assert result is None

    def test_empty_string_returns_none(self):
        """Test that empty string module ID returns None."""
        result = _get_module_permission_path("")
        assert result is None

    def test_case_sensitive_module_id(self):
        """Test that module ID is case-sensitive."""
        # Wrong case should return None
        result = _get_module_permission_path("Professional-Travel")
        assert result is None


class TestCheckModulePermission:
    """Tests for check_module_permission async function."""

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_allow(self, mock_query_policy):
        """Test check_module_permission when permission is granted."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(unit="123"))]

        # Mock policy allows access
        mock_query_policy.return_value = {
            "allow": True,
            "reason": "Permission granted",
        }

        # Should not raise exception
        await check_module_permission(user, "professional-travel", "view")

        # Verify query_policy was called correctly
        mock_query_policy.assert_awaited_once()
        call_args = mock_query_policy.call_args
        assert call_args[0][0] == "authz/permission/check"
        assert call_args[0][1]["path"] == "modules.professional_travel"
        assert call_args[0][1]["action"] == "view"

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_deny(self, mock_query_policy):
        """Test check_module_permission when permission is denied."""
        user = MagicMock()
        user.id = "user-456"
        user.email = "test@example.com"
        user.roles = []

        # Mock policy denies access
        mock_query_policy.return_value = {
            "allow": False,
            "reason": "Insufficient permissions",
        }

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await check_module_permission(
                user, "equipment-electric-consumption", "edit"
            )

        assert exc_info.value.status_code == 403
        assert "Permission denied" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_check_module_permission_no_path_required(self):
        """Test check_module_permission for module without permission path."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = []

        # Module without permission requirement (returns None from mapping)
        # Should not raise exception and allow access
        await check_module_permission(user, "unknown-module", "view")

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_view_action(self, mock_query_policy):
        """Test check_module_permission with view action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(unit="123"))]

        mock_query_policy.return_value = {"allow": True}

        await check_module_permission(user, "infrastructure", "view")

        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "view"

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_edit_action(self, mock_query_policy):
        """Test check_module_permission with edit action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(unit="123"))]

        mock_query_policy.return_value = {"allow": True}

        await check_module_permission(user, "purchase", "edit")

        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "edit"

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_user_without_roles(self, mock_query_policy):
        """Test check_module_permission for user with None roles."""
        user = MagicMock()
        user.id = "user-789"
        user.email = "noroles@example.com"
        user.roles = None

        mock_query_policy.return_value = {
            "allow": False,
            "reason": "No roles assigned",
        }

        with pytest.raises(HTTPException) as exc_info:
            await check_module_permission(user, "professional-travel", "view")

        assert exc_info.value.status_code == 403

        # Verify roles were passed as empty list
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["user"]["roles"] == []

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_different_modules(self, mock_query_policy):
        """Test check_module_permission with various modules."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(unit="123"))]

        mock_query_policy.return_value = {"allow": True}

        modules = [
            ("professional-travel", "modules.professional_travel"),
            ("equipment-electric-consumption", "modules.equipment"),
            ("my-lab", "modules.headcount"),
            ("external-cloud-and-ai", "modules.external_cloud_and_ai"),
        ]

        for module_id, expected_path in modules:
            await check_module_permission(user, module_id, "view")

            # Verify correct permission path was used
            call_args = mock_query_policy.call_args
            assert call_args[0][1]["path"] == expected_path

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_no_allow_key(self, mock_query_policy):
        """Test check_module_permission when policy returns no 'allow' key."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(unit="123"))]

        # Policy returns dict without 'allow' key
        mock_query_policy.return_value = {"reason": "Unknown"}

        # Should raise exception (defaults to False when 'allow' is missing)
        with pytest.raises(HTTPException):
            await check_module_permission(user, "professional-travel", "view")


class TestQueryPolicyPermissionCheck:
    """Tests for query_policy with permission check policy."""

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_with_user_object(self):
        """Test permission check policy with user dict and roles."""
        input_data = {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "roles": [
                    {
                        "role": RoleName.CO2_USER_PRINCIPAL.value,
                        "on": {"provider_code": "123"},
                    }
                ],
            },
            "path": "modules.professional_travel",
            "action": "view",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is True
        assert "Permission granted" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_denied(self):
        """Test permission check policy when permission denied."""
        input_data = {
            "user": {
                "id": "user-456",
                "email": "test@example.com",
                "roles": [],
            },
            "path": "modules.professional_travel",
            "action": "edit",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is False
        assert "Permission denied" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_missing_user(self):
        """Test permission check policy with missing user."""
        input_data = {
            "path": "modules.professional_travel",
            "action": "view",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is False
        assert "Missing user" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_missing_path(self):
        """Test permission check policy with missing path."""
        input_data = {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "roles": [],
            },
            "action": "view",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is False
        assert "missing" in result["reason"].lower()


class TestQueryPolicyDataFilter:
    """Tests for query_policy with data filter policies."""

    @pytest.mark.asyncio
    async def test_query_policy_data_list_global_scope(self):
        """Test data list policy for user with global scope."""
        input_data = {
            "user": {
                "id": 1,
                "email": "admin@example.com",
                "roles": [
                    {"role": RoleName.CO2_SUPERADMIN.value, "on": {"scope": "global"}}
                ],
            },
            "resource_type": "headcount",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is True
        assert result["filters"]["scope"] == "global"
        assert "unit_ids" not in result["filters"]

    @pytest.mark.asyncio
    async def test_query_policy_data_list_unit_scope(self):
        """Test data list policy for user with unit scope."""
        input_data = {
            "user": {
                "id": 2,
                "email": "principal@example.com",
                "roles": [
                    {
                        "role": RoleName.CO2_USER_PRINCIPAL.value,
                        "on": {"provider_code": "123"},
                    }
                ],
            },
            "resource_type": "equipment",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is True
        assert result["filters"]["scope"] == "unit"
        assert "123" in result["filters"]["unit_ids"]

    @pytest.mark.asyncio
    async def test_query_policy_data_list_own_scope(self):
        """Test data list policy for standard user (own scope)."""
        input_data = {
            "user": {
                "id": 3,
                "email": "standard@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is True
        assert result["filters"]["scope"] == "own"
        assert result["filters"]["user_id"] == 3

    @pytest.mark.asyncio
    async def test_query_policy_data_list_missing_user(self):
        """Test data list policy with missing user."""
        input_data = {
            "resource_type": "headcount",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is False
        assert "Missing user" in result["reason"]


class TestQueryPolicyResourceAccess:
    """Tests for query_policy with resource access policy."""

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_api_provider_denied(self):
        """Test resource access denies edit for API trips."""
        input_data = {
            "user": {
                "id": 1,
                "email": "user@example.com",
                "roles": [
                    {
                        "role": RoleName.CO2_USER_PRINCIPAL.value,
                        "on": {"provider_code": "123"},
                    }
                ],
            },
            "resource_type": "professional_travel",
            "resource": {
                "id": 100,
                "provider": "api",
                "unit_id": "123",
            },
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is False
        assert "read-only" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_global_scope_allow(self):
        """Test resource access allows for global scope admin."""
        input_data = {
            "user": {
                "id": 1,
                "email": "admin@example.com",
                "roles": [
                    {"role": RoleName.CO2_SUPERADMIN.value, "on": {"scope": "global"}}
                ],
            },
            "resource_type": "professional_travel",
            "resource": {
                "id": 100,
                "provider": "manual",
                "created_by": 999,
                "unit_id": "456",
            },
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is True
        assert "Global scope" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_owner_allow(self):
        """Test resource access allows user to edit their own resource."""
        input_data = {
            "user": {
                "id": 123,
                "email": "user@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
            "resource": {
                "id": 100,
                "provider": "manual",
                "created_by": 123,
                "unit_id": "456",
            },
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is True
        assert "Owner access" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_missing_resource(self):
        """Test resource access with missing resource."""
        input_data = {
            "user": {
                "id": 1,
                "email": "user@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is False
        assert "Missing resource" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_unknown_resource_type(self):
        """Test resource access with unknown resource type."""
        input_data = {
            "user": {
                "id": 1,
                "email": "user@example.com",
                "roles": [],
            },
            "resource_type": "unknown_type",
            "resource": {"id": 1},
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is False
        assert "No policy defined" in result["reason"]


class TestQueryPolicyLegacy:
    """Tests for query_policy with legacy/fallback policy paths."""

    @pytest.mark.asyncio
    async def test_query_policy_legacy_allow(self):
        """Test legacy policy path returns allow."""
        input_data = {"filters": {"unit_ids": ["123"]}}

        result = await query_policy("authz/unit/list", input_data)

        assert result["allow"] is True
        assert "filters" in result

    @pytest.mark.asyncio
    async def test_query_policy_legacy_no_filters(self):
        """Test legacy policy path with no filters."""
        input_data = {}

        result = await query_policy("authz/resource/list", input_data)

        assert result["allow"] is True
        assert result["filters"] == {}
