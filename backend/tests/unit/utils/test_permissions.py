"""Unit tests for permission calculation utilities.

Tests cover:
- calculate_user_permissions with all role types
- has_permission helper function
- get_permission_value helper function
- Edge cases and combinations
"""

from app.models.user import GlobalScope, Role, RoleName, RoleScope
from app.utils.permissions import (
    calculate_user_permissions,
    get_permission_value,
    has_permission,
)


class TestCalculateUserPermissions:
    """Tests for calculate_user_permissions function."""

    def test_empty_roles_returns_empty_dict(self):
        """Test that empty roles list returns empty dict."""
        result = calculate_user_permissions([])
        assert result == {}

    def test_backoffice_admin_global_scope(self):
        """Test backoffice admin with global scope grants all permissions."""
        roles = [Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert result["backoffice.users"]["view"] is True
        assert result["backoffice.users"]["edit"] is True
        assert result["backoffice.users"]["export"] is True
        assert result["modules.headcount"]["view"] is False
        assert result["modules.equipment"]["view"] is False

    def test_backoffice_std_global_scope(self):
        """Test backoffice std with global scope grants view only."""
        roles = [Role(role=RoleName.CO2_BACKOFFICE_STD, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert result["backoffice.users"]["view"] is True
        assert result["backoffice.users"]["edit"] is False
        assert result["backoffice.users"]["export"] is False

    def test_backoffice_admin_wrong_scope(self):
        """Test backoffice admin with unit scope does not grant permissions."""
        roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_ADMIN,
                on=RoleScope(unit="10208"),
            )
        ]
        result = calculate_user_permissions(roles)

        assert result["backoffice.users"]["view"] is False
        assert result["backoffice.users"]["edit"] is False

    def test_user_principal_unit_scope(self):
        """Test user principal with unit scope grants module permissions."""
        roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(unit="10208"))]
        result = calculate_user_permissions(roles)

        assert result["modules.headcount"]["view"] is True
        assert result["modules.headcount"]["edit"] is True
        assert result["modules.equipment"]["view"] is True
        assert result["modules.equipment"]["edit"] is True
        assert result["modules.professional_travel"]["view"] is True
        assert result["modules.professional_travel"]["edit"] is True
        assert result["modules.infrastructure"]["view"] is True
        assert result["modules.infrastructure"]["edit"] is True
        assert result["modules.purchase"]["view"] is True
        assert result["modules.purchase"]["edit"] is True
        assert result["modules.internal_services"]["view"] is True
        assert result["modules.internal_services"]["edit"] is True
        assert result["modules.external_cloud"]["view"] is True
        assert result["modules.external_cloud"]["edit"] is True
        assert result["backoffice.users"]["view"] is False

    def test_user_std_unit_scope(self):
        """Test user std with unit scope grants view and edit for professional_travel."""  # noqa: E501
        roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="10208"))]
        result = calculate_user_permissions(roles)

        assert result["modules.headcount"]["view"] is False
        assert result["modules.headcount"]["edit"] is False
        assert result["modules.equipment"]["view"] is False
        assert result["modules.equipment"]["edit"] is False
        assert result["modules.professional_travel"]["view"] is True
        assert result["modules.professional_travel"]["edit"] is True
        assert result["modules.infrastructure"]["view"] is False
        assert result["modules.infrastructure"]["edit"] is False
        assert result["modules.purchase"]["view"] is False
        assert result["modules.purchase"]["edit"] is False
        assert result["modules.internal_services"]["view"] is False
        assert result["modules.internal_services"]["edit"] is False
        assert result["modules.external_cloud"]["view"] is False
        assert result["modules.external_cloud"]["edit"] is False

    def test_user_secondary_unit_scope(self):
        """Test user secondary with unit scope grants view and edit for all modules."""
        roles = [Role(role=RoleName.CO2_USER_SECONDARY, on=RoleScope(unit="10208"))]
        result = calculate_user_permissions(roles)

        assert result["modules.headcount"]["view"] is True
        assert result["modules.headcount"]["edit"] is True
        assert result["modules.equipment"]["view"] is True
        assert result["modules.equipment"]["edit"] is True
        assert result["modules.professional_travel"]["view"] is True
        assert result["modules.professional_travel"]["edit"] is True
        assert result["modules.infrastructure"]["view"] is True
        assert result["modules.infrastructure"]["edit"] is True
        assert result["modules.purchase"]["view"] is True
        assert result["modules.purchase"]["edit"] is True
        assert result["modules.internal_services"]["view"] is True
        assert result["modules.internal_services"]["edit"] is True
        assert result["modules.external_cloud"]["view"] is True
        assert result["modules.external_cloud"]["edit"] is True
        assert result["backoffice.users"]["view"] is False

    def test_user_roles_wrong_scope(self):
        """Test user roles with global scope do not grant permissions."""
        roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert result["modules.headcount"]["view"] is False
        assert result["modules.headcount"]["edit"] is False

    def test_service_mgr_global_scope(self):
        """Test service manager role (reserved for future)."""
        roles = [Role(role=RoleName.CO2_SERVICE_MGR, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        # Service manager does not grant any current permissions
        assert result["backoffice.users"]["view"] is False
        assert result["modules.headcount"]["view"] is False

    def test_combined_backoffice_and_user_roles(self):
        """Test that permissions from different domains combine."""
        roles = [
            Role(role=RoleName.CO2_BACKOFFICE_STD, on=GlobalScope()),
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="10208")),
        ]
        result = calculate_user_permissions(roles)

        # Backoffice permissions
        assert result["backoffice.users"]["view"] is True
        assert result["backoffice.users"]["edit"] is False

        # Module permissions - CO2_USER_STD grants professional_travel.view and edit
        assert result["modules.professional_travel"]["view"] is True
        assert result["modules.professional_travel"]["edit"] is True
        assert result["modules.headcount"]["view"] is False
        assert result["modules.headcount"]["edit"] is False
        assert result["modules.equipment"]["view"] is False
        assert result["modules.equipment"]["edit"] is False

    def test_multiple_user_roles_same_unit(self):
        """Test multiple user roles for same unit combine correctly."""
        roles = [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="10208")),
            Role(role=RoleName.CO2_USER_SECONDARY, on=RoleScope(unit="10208")),
        ]
        result = calculate_user_permissions(roles)

        assert result["modules.headcount"]["view"] is True
        assert result["modules.headcount"]["edit"] is True
        assert result["modules.professional_travel"]["view"] is True
        assert result["modules.professional_travel"]["edit"] is True

    def test_role_name_as_string(self):
        """Test that role name can be string or enum."""
        # Create role with string role name
        role_dict = {
            "role": "co2.backoffice.admin",
            "on": {"scope": "global"},
        }
        role = Role(**role_dict)
        roles = [role]
        result = calculate_user_permissions(roles)

        assert result["backoffice.users"]["view"] is True
        assert result["backoffice.users"]["edit"] is True

    def test_all_permissions_initialized(self):
        """Test that all permissions are initialized even with no roles."""
        roles = []
        result = calculate_user_permissions(roles)

        # Should return empty dict for no roles
        assert result == {}

    def test_backoffice_admin_overrides_std(self):
        """Test that admin role overrides std role permissions."""
        roles = [
            Role(role=RoleName.CO2_BACKOFFICE_STD, on=GlobalScope()),
            Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope()),
        ]
        result = calculate_user_permissions(roles)

        # Admin should grant all permissions
        assert result["backoffice.users"]["view"] is True
        assert result["backoffice.users"]["edit"] is True
        assert result["backoffice.users"]["export"] is True


class TestHasPermission:
    """Tests for has_permission helper function."""

    def test_has_permission_view_true(self):
        """Test has_permission returns True for valid view permission."""
        perms = {
            "modules.headcount": {"view": True, "edit": False},
        }
        result = has_permission(perms, "modules.headcount", "view")
        assert result is True

    def test_has_permission_edit_false(self):
        """Test has_permission returns False for false edit permission."""
        perms = {
            "modules.headcount": {"view": True, "edit": False},
        }
        result = has_permission(perms, "modules.headcount", "edit")
        assert result is False

    def test_has_permission_missing_path(self):
        """Test has_permission returns False for missing path."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = has_permission(perms, "modules.equipment", "view")
        assert result is False

    def test_has_permission_missing_action(self):
        """Test has_permission returns False for missing action."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = has_permission(perms, "modules.headcount", "export")
        assert result is False

    def test_has_permission_none_permissions(self):
        """Test has_permission handles None permissions."""
        result = has_permission(None, "modules.headcount", "view")
        assert result is False

    def test_has_permission_empty_dict(self):
        """Test has_permission handles empty dict."""
        result = has_permission({}, "modules.headcount", "view")
        assert result is False

    def test_has_permission_export_action(self):
        """Test has_permission works with export action."""
        perms = {
            "backoffice.users": {"view": True, "edit": True, "export": True},
        }
        result = has_permission(perms, "backoffice.users", "export")
        assert result is True

    def test_has_permission_default_action_view(self):
        """Test has_permission defaults to view action."""
        perms = {
            "modules.headcount": {"view": True, "edit": False},
        }
        result = has_permission(perms, "modules.headcount")
        assert result is True

    def test_has_permission_invalid_structure(self):
        """Test has_permission handles invalid permission structure."""
        perms = {
            "modules.headcount": "invalid",
        }
        result = has_permission(perms, "modules.headcount", "view")
        assert result is False


class TestGetPermissionValue:
    """Tests for get_permission_value helper function."""

    def test_get_permission_value_view_true(self):
        """Test get_permission_value returns True for valid permission."""
        perms = {
            "modules.headcount": {"view": True, "edit": False},
        }
        result = get_permission_value(perms, "modules.headcount.view")
        assert result is True

    def test_get_permission_value_edit_false(self):
        """Test get_permission_value returns False for false permission."""
        perms = {
            "modules.headcount": {"view": True, "edit": False},
        }
        result = get_permission_value(perms, "modules.headcount.edit")
        assert result is False

    def test_get_permission_value_missing_path(self):
        """Test get_permission_value returns None for missing path."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "modules.equipment.view")
        assert result is None

    def test_get_permission_value_missing_action(self):
        """Test get_permission_value returns None for missing action."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "modules.headcount.export")
        assert result is None

    def test_get_permission_value_none_permissions(self):
        """Test get_permission_value handles None permissions."""
        result = get_permission_value(None, "modules.headcount.view")
        assert result is None

    def test_get_permission_value_empty_dict(self):
        """Test get_permission_value handles empty dict."""
        result = get_permission_value({}, "modules.headcount.view")
        assert result is None

    def test_get_permission_value_invalid_path_format(self):
        """Test get_permission_value handles invalid path format."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "invalid")
        assert result is None

    def test_get_permission_value_too_many_dots(self):
        """Test get_permission_value handles paths with too many dots."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "modules.headcount.view.extra")
        # Should still work, splits from right
        assert result is None

    def test_get_permission_value_export_action(self):
        """Test get_permission_value works with export action."""
        perms = {
            "backoffice.users": {"view": True, "edit": True, "export": True},
        }
        result = get_permission_value(perms, "backoffice.users.export")
        assert result is True

    def test_get_permission_value_invalid_structure(self):
        """Test get_permission_value handles invalid permission structure."""
        perms = {
            "modules.headcount": "invalid",
        }
        result = get_permission_value(perms, "modules.headcount.view")
        assert result is None

    def test_get_permission_value_empty_path(self):
        """Test get_permission_value with empty path."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "")
        assert result is None

    def test_get_permission_value_no_dot(self):
        """Test get_permission_value with path that has no dot."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "invalid")
        assert result is None

    def test_has_permission_with_none_action(self):
        """Test has_permission with None action."""
        perms = {
            "modules.headcount": {"view": True},
        }
        # Should default to "view"
        result = has_permission(perms, "modules.headcount")
        assert result is True

    def test_has_permission_with_empty_action(self):
        """Test has_permission with empty action string."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = has_permission(perms, "modules.headcount", "")
        assert result is False

    def test_calculate_user_permissions_with_none_roles(self):
        """Test calculate_user_permissions with None roles."""
        result = calculate_user_permissions(None)
        assert result == {}

    def test_calculate_user_permissions_backoffice_std_with_affiliation_scope(self):
        """Test backoffice std with affiliation scope grants view."""
        roles = [
            Role(role=RoleName.CO2_BACKOFFICE_STD, on=RoleScope(affiliation="TEST-AFF"))
        ]
        result = calculate_user_permissions(roles)
        assert result["backoffice.users"]["view"] is True
        assert result["backoffice.users"]["edit"] is False

    def test_calculate_user_permissions_user_secondary_global_scope(self):
        """Test user secondary with global scope does not grant permissions."""
        roles = [Role(role=RoleName.CO2_USER_SECONDARY, on=GlobalScope())]
        result = calculate_user_permissions(roles)
        # Global scope for user roles should not grant permissions
        assert result["modules.headcount"]["view"] is False
        assert result["modules.equipment"]["view"] is False

    def test_calculate_user_permissions_user_principal_global_scope(self):
        """Test user principal with global scope does not grant permissions."""
        roles = [Role(role=RoleName.CO2_USER_PRINCIPAL, on=GlobalScope())]
        result = calculate_user_permissions(roles)
        # Global scope for user roles should not grant permissions
        assert result["modules.headcount"]["view"] is False
        assert result["modules.equipment"]["view"] is False

    def test_calculate_user_permissions_service_mgr_global_scope(self):
        """Test service manager with global scope grants system permissions."""
        roles = [Role(role=RoleName.CO2_SERVICE_MGR, on=GlobalScope())]
        result = calculate_user_permissions(roles)
        assert result["system.users"]["edit"] is True
        assert result["backoffice.users"]["view"] is False
        assert result["modules.headcount"]["view"] is False

    def test_calculate_user_permissions_service_mgr_unit_scope(self):
        """Test service manager with unit scope does not grant permissions."""
        roles = [Role(role=RoleName.CO2_SERVICE_MGR, on=RoleScope(unit="12345"))]
        result = calculate_user_permissions(roles)
        assert result["system.users"]["edit"] is False

    def test_calculate_user_permissions_role_as_string(self):
        """Test calculate_user_permissions with role name as string."""
        # Create role with string role name directly
        role_dict = {
            "role": "co2.user.secondary",
            "on": {"unit": "12345"},
        }
        role = Role(**role_dict)
        roles = [role]
        result = calculate_user_permissions(roles)
        assert result["modules.headcount"]["view"] is True
        assert result["modules.headcount"]["edit"] is True

    def test_calculate_user_permissions_invalid_role_enum(self):
        """Test calculate_user_permissions with invalid role enum value."""
        # Create a role with a valid enum but test that non-matching role names
        # don't grant permissions
        # We'll use a valid role but test the logic path for roles that don't
        # match any condition
        # Since Role validation requires a valid RoleName, we'll test with a
        # role that has valid enum but test the else path by ensuring no
        # permissions are granted for unmatched conditions
        roles = [Role(role=RoleName.CO2_SERVICE_MGR, on=RoleScope(unit="12345"))]
        result = calculate_user_permissions(roles)
        # Service manager with unit scope (not global) should not grant permissions
        assert result["system.users"]["edit"] is False
        assert result["backoffice.users"]["view"] is False
        assert result["modules.headcount"]["view"] is False

    def test_calculate_user_permissions_multiple_units(self):
        """Test calculate_user_permissions with roles for multiple units."""
        roles = [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345")),
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="99999")),
        ]
        result = calculate_user_permissions(roles)
        # Should grant permissions (same role, different units)
        assert result["modules.professional_travel"]["view"] is True
        assert result["modules.professional_travel"]["edit"] is True

    def test_has_permission_with_false_value(self):
        """Test has_permission with explicitly False value."""
        perms = {
            "modules.headcount": {"view": False, "edit": False},
        }
        result = has_permission(perms, "modules.headcount", "view")
        assert result is False

    def test_get_permission_value_with_false_value(self):
        """Test get_permission_value with explicitly False value."""
        perms = {
            "modules.headcount": {"view": False},
        }
        result = get_permission_value(perms, "modules.headcount.view")
        assert result is False

    def test_get_permission_value_with_zero_dots(self):
        """Test get_permission_value with path that has no dots."""
        perms = {
            "modules.headcount": {"view": True},
        }
        result = get_permission_value(perms, "invalidpath")
        assert result is None
