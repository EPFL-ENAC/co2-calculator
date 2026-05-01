"""Unit tests for permission calculation utilities.

Tests cover:
- calculate_user_permissions with all role types
- has_permission helper function
- get_permission_value helper function
- Edge cases and combinations
"""

from app.models.user import (
    GlobalScope,
    Role,
    RoleName,
    RoleScope,
    calculate_user_permissions,
)
from app.utils.permissions import (
    has_permission,
)


class TestCalculateUserPermissions:
    """Tests for calculate_user_permissions function."""

    def test_empty_roles_returns_empty_dict(self):
        """Test that empty roles list returns empty dict."""
        result = calculate_user_permissions([])
        assert result == {}

    def test_superadmin_global_scope(self):
        """Test superadmin with global scope grants all permissions."""
        roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert "view" in result["backoffice.users"]
        assert "edit" in result["backoffice.users"]
        assert "export" in result["backoffice.users"]
        assert "edit" in result["system.users"]
        assert "modules.headcount" not in result
        assert "modules.equipment" not in result

    def test_backoffice_metier_global_scope(self):
        """Test backoffice metier with global scope grants full backoffice access."""
        roles = [Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert "view" in result["backoffice.users"]
        assert "edit" in result["backoffice.users"]
        assert "export" in result["backoffice.users"]

    def test_superadmin_wrong_scope(self):
        """Test superadmin with unit scope does not grant permissions."""
        roles = [
            Role(
                role=RoleName.CO2_SUPERADMIN,
                on=RoleScope(unit="10208"),
            )
        ]
        result = calculate_user_permissions(roles)

        assert "backoffice.users" not in result

    def test_user_principal_unit_scope(self):
        """Test user principal with unit scope grants module permissions."""
        roles = [
            Role(
                role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(institutional_id="10208")
            )
        ]
        result = calculate_user_permissions(roles)

        assert "view" in result["modules.headcount/10208"]
        assert "edit" in result["modules.headcount/10208"]
        assert "view" in result["modules.equipment/10208"]
        assert "edit" in result["modules.equipment/10208"]
        assert "view" in result["modules.professional_travel/10208"]
        assert "edit" in result["modules.professional_travel/10208"]
        assert "view" in result["modules.buildings/10208"]
        assert "edit" in result["modules.buildings/10208"]
        assert "view" in result["modules.purchase/10208"]
        assert "edit" in result["modules.purchase/10208"]
        assert "view" in result["modules.research_facilities/10208"]
        assert "edit" in result["modules.research_facilities/10208"]
        assert "view" in result["modules.external_cloud_and_ai/10208"]
        assert "edit" in result["modules.external_cloud_and_ai/10208"]
        # Principal also gets backoffice.users.edit for unit-scoped role assignment
        assert "edit" in result["backoffice.users"]

    def test_user_std_unit_scope(self):
        """Test user std with unit scope grants view and edit for professional_travel."""  # noqa: E501
        roles = [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="10208"))
        ]
        result = calculate_user_permissions(roles)

        assert "modules.headcount/10208" not in result
        assert "modules.equipment/10208" not in result
        assert "modules.professional_travel/10208" in result
        assert "view" in result["modules.professional_travel/10208"]
        assert "edit" in result["modules.professional_travel/10208"]
        assert "modules.buildings/10208" not in result
        assert "modules.purchase/10208" not in result
        assert "modules.research_facilities/10208" not in result
        assert "modules.external_cloud_and_ai/10208" in result
        assert "view" in result["modules.external_cloud_and_ai/10208"]
        assert "edit" in result["modules.external_cloud_and_ai/10208"]

    def test_user_roles_wrong_scope(self):
        """Test user roles with global scope do not grant permissions."""
        roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert "modules.headcount/10208" not in result

    def test_combined_backoffice_and_user_roles(self):
        """Test that permissions from different domains combine."""
        roles = [
            Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope()),
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="10208")),
        ]
        result = calculate_user_permissions(roles)

        # Backoffice permissions
        assert "backoffice.users" in result
        assert "view" in result["backoffice.users"]
        assert "edit" in result["backoffice.users"]

        # Module permissions - CO2_USER_STD grants professional_travel.view and edit
        assert "view" in result["modules.professional_travel/10208"]
        assert "edit" in result["modules.professional_travel/10208"]
        assert "modules.headcount/10208" not in result
        assert "modules.equipment/10208" not in result

    def test_multiple_user_roles_same_unit(self):
        """Test multiple user roles for same unit combine correctly."""
        roles = [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="10208")),
            Role(
                role=RoleName.CO2_USER_PRINCIPAL, on=RoleScope(institutional_id="10208")
            ),
        ]
        result = calculate_user_permissions(roles)

        assert "view" in result["modules.headcount/10208"]
        assert "edit" in result["modules.headcount/10208"]
        assert "view" in result["modules.professional_travel/10208"]
        assert "edit" in result["modules.professional_travel/10208"]

    def test_role_name_as_string(self):
        """Test that role name can be string or enum."""
        # Create role with string role name
        role_dict = {
            "role": f"{RoleName.CO2_SUPERADMIN.value}",
            "on": {"scope": "global"},
        }
        role = Role(**role_dict)
        roles = [role]
        result = calculate_user_permissions(roles)

        assert "view" in result["backoffice.users"]
        assert "edit" in result["backoffice.users"]

    def test_all_permissions_initialized(self):
        """Test that all permissions are initialized even with no roles."""
        roles = []
        result = calculate_user_permissions(roles)

        # Should return empty dict for no roles
        assert result == {}

    def test_superadmin_has_all_backoffice(self):
        """Test that superadmin role grants all backoffice permissions."""
        roles = [
            Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope()),
        ]
        result = calculate_user_permissions(roles)

        # Superadmin should grant all backoffice permissions
        assert "view" in result["backoffice.users"]
        assert "edit" in result["backoffice.users"]
        assert "export" in result["backoffice.users"]


class TestHasPermission:
    """Tests for has_permission helper function."""

    def test_has_permission_view_true(self):
        """Test has_permission returns True for valid view permission."""
        perms = {
            "modules.headcount": ["view", "edit"],
        }
        result = has_permission(perms, "modules.headcount", "view")
        assert result is True

    def test_has_permission_edit_false(self):
        """Test has_permission returns False for false edit permission."""
        perms = {
            "modules.headcount": ["view"],
        }
        result = has_permission(perms, "modules.headcount", "edit")
        assert result is False

    def test_has_permission_missing_path(self):
        """Test has_permission returns False for missing path."""
        perms = {
            "modules.headcount": ["view"],
        }
        result = has_permission(perms, "modules.equipment", "view")
        assert result is False

    def test_has_permission_missing_action(self):
        """Test has_permission returns False for missing action."""
        perms = {
            "modules.headcount": ["view"],
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
            "backoffice.users": ["view", "edit", "export"],
        }
        result = has_permission(perms, "backoffice.users", "export")
        assert result is True

    def test_has_permission_default_action_view(self):
        """Test has_permission defaults to view action."""
        perms = {
            "modules.headcount": ["view", "edit"],
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
