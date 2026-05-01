"""Unit tests for UserBase.calculate_permissions method.

Tests cover:
- calculate_permissions method on UserBase
- Edge cases and various role combinations
"""

from app.models.user import GlobalScope, Role, RoleName, RoleScope, UserBase


class TestUserBaseCalculatePermissions:
    """Tests for UserBase.calculate_permissions method."""

    def test_calculate_permissions_empty_roles(self):
        """Test calculate_permissions with no roles."""
        user_base = UserBase()
        user_base.roles_raw = None
        perms = user_base.calculate_permissions()
        assert perms == {}

    def test_calculate_permissions_with_roles(self):
        """Test calculate_permissions with roles set via property."""
        user_base = UserBase()
        user_base.roles = [
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="12345"))
        ]
        perms = user_base.calculate_permissions()
        assert "modules.professional_travel/12345" in perms
        assert "view" in perms["modules.professional_travel/12345"]

    def test_calculate_permissions_with_dict_roles(self):
        """Test calculate_permissions with roles_raw as dicts."""
        user_base = UserBase()
        user_base.roles_raw = [
            {"role": f"{RoleName.CO2_USER_STD.value}", "on": {"institutional_id": "12345"}},
        ]
        perms = user_base.calculate_permissions()
        assert "modules.professional_travel/12345" in perms
        assert "view" in perms["modules.professional_travel/12345"]

    def test_calculate_permissions_superadmin(self):
        """Test calculate_permissions with superadmin role."""
        user_base = UserBase()
        user_base.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        perms = user_base.calculate_permissions()
        assert "view" in perms["backoffice.users"]
        assert "edit" in perms["backoffice.users"]
        assert "export" in perms["backoffice.users"]

    def test_calculate_permissions_multiple_roles(self):
        """Test calculate_permissions with multiple roles."""
        user_base = UserBase()
        user_base.roles = [
            Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope()),
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(institutional_id="12345")),
        ]
        perms = user_base.calculate_permissions()
        # Should have both backoffice and module permissions
        assert "view" in perms["backoffice.users"]
        assert "view" in perms["modules.professional_travel/12345"]
