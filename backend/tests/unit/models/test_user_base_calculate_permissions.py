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
        user_base.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        perms = user_base.calculate_permissions()
        assert "modules.professional_travel" in perms
        assert perms["modules.professional_travel"]["view"] is True

    def test_calculate_permissions_with_dict_roles(self):
        """Test calculate_permissions with roles_raw as dicts."""
        user_base = UserBase()
        user_base.roles_raw = [
            {"role": "co2.user.std", "on": {"unit": "12345"}},
        ]
        perms = user_base.calculate_permissions()
        assert "modules.professional_travel" in perms
        assert perms["modules.professional_travel"]["view"] is True

    def test_calculate_permissions_backoffice_admin(self):
        """Test calculate_permissions with backoffice admin role."""
        user_base = UserBase()
        user_base.roles = [Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope())]
        perms = user_base.calculate_permissions()
        assert perms["backoffice.users"]["view"] is True
        assert perms["backoffice.users"]["edit"] is True
        assert perms["backoffice.users"]["export"] is True

    def test_calculate_permissions_multiple_roles(self):
        """Test calculate_permissions with multiple roles."""
        user_base = UserBase()
        user_base.roles = [
            Role(role=RoleName.CO2_BACKOFFICE_STD, on=GlobalScope()),
            Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345")),
        ]
        perms = user_base.calculate_permissions()
        # Should have both backoffice and module permissions
        assert perms["backoffice.users"]["view"] is True
        assert perms["modules.professional_travel"]["view"] is True
