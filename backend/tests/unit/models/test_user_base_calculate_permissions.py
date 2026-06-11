"""Unit tests for UserBase.calculate_permissions method.

Tests cover:
- calculate_permissions method on UserBase
- Edge cases and various role combinations
"""

from app.models.user import (
    AffiliationScope,
    GlobalScope,
    OwnScope,
    Role,
    RoleName,
    UserBase,
)


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
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="12345"))
        ]
        perms = user_base.calculate_permissions()
        assert "modules.professional_travel/12345/own" in perms
        assert "view" in perms["modules.professional_travel/12345/own"]

    def test_calculate_permissions_with_dict_roles(self):
        """Test calculate_permissions with roles_raw as dicts."""
        user_base = UserBase()
        user_base.roles_raw = [
            {
                "role": f"{RoleName.CO2_USER_STD.value}",
                "on": {"kind": "own", "institutional_id": "12345"},
            },
        ]
        perms = user_base.calculate_permissions()
        assert "modules.professional_travel/12345/own" in perms
        assert "view" in perms["modules.professional_travel/12345/own"]

    def test_calculate_permissions_superadmin(self):
        """Test calculate_permissions with superadmin role."""
        user_base = UserBase()
        user_base.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        perms = user_base.calculate_permissions()
        assert "view" in perms["backoffice.users"]
        assert "edit" in perms["backoffice.users"]
        assert "export" in perms["backoffice.users"]
        # Page-driven super-admin keys replace the former system.users (#862).
        assert "edit" in perms["backoffice.configuration"]
        assert "view" in perms["backoffice.logs"]
        assert "edit" in perms["backoffice.pipeline_operations"]
        assert "edit" in perms["backoffice.ui_texts"]
        assert "system.users" not in perms

    def test_calculate_permissions_multiple_roles(self):
        """Test calculate_permissions with multiple roles.

        CO2_BACKOFFICE_METIER is sub-perimeter-bound: reporting is
        affiliation-scoped while users/documentation/ui_texts are scope-less
        (#862). Combined with CO2_USER_STD it also yields the std module key."""
        user_base = UserBase()
        user_base.roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=AffiliationScope(affiliation="SV"),
            ),
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="12345")),
        ]
        perms = user_base.calculate_permissions()
        assert "view" in perms["backoffice.reporting/SV"]
        assert "view" in perms["backoffice.users"]
        assert "backoffice.users/SV" not in perms
        assert "view" in perms["modules.professional_travel/12345/own"]
