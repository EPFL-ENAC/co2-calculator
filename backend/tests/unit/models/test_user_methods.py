"""Unit tests for User model methods.

Tests cover:
- UserBase roles property and setter
- User.calculate_permissions method
- User.has_role method (deprecated but still used)
- User.has_role_on method (deprecated but still used)
- User.has_role_global method (deprecated but still used)
"""

import warnings

from app.models.user import GlobalScope, Role, RoleName, RoleScope, User, UserBase


class TestUserBaseRolesProperty:
    """Tests for UserBase roles property and setter."""

    def test_roles_property_empty(self):
        """Test roles property with empty roles_raw."""
        user_base = UserBase()
        user_base.roles_raw = None
        assert user_base.roles == []

    def test_roles_property_with_dict(self):
        """Test roles property with dict roles_raw."""
        user_base = UserBase()
        user_base.roles_raw = [
            {"role": f"{RoleName.CO2_USER_STD.value}", "on": {"unit": "12345"}},
        ]
        roles = user_base.roles
        assert len(roles) == 1
        assert isinstance(roles[0], Role)
        assert roles[0].role == RoleName.CO2_USER_STD

    def test_roles_property_with_role_objects(self):
        """Test roles property with Role objects in roles_raw."""
        user_base = UserBase()
        role = Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))
        user_base.roles_raw = [role]
        roles = user_base.roles
        assert len(roles) == 1
        assert roles[0] == role

    def test_roles_property_mixed_dict_and_objects(self):
        """Test roles property with mixed dict and Role objects."""
        user_base = UserBase()
        role_obj = Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))
        role_dict = {
            "role": f"{RoleName.CO2_USER_PRINCIPAL.value}",
            "on": {"unit": "99999"},
        }
        user_base.roles_raw = [role_obj, role_dict]
        roles = user_base.roles
        assert len(roles) == 2
        assert isinstance(roles[0], Role)
        assert isinstance(roles[1], Role)

    def test_roles_setter(self):
        """Test roles setter converts Role objects to dict."""
        user_base = UserBase()
        roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        user_base.roles = roles
        assert user_base.roles_raw is not None
        assert len(user_base.roles_raw) == 1
        assert user_base.roles_raw[0]["role"] == f"{RoleName.CO2_USER_STD.value}"
        assert user_base.roles_raw[0]["on"]["unit"] == "12345"

    def test_roles_setter_with_enum(self):
        """Test roles setter handles RoleName enum correctly."""
        user_base = UserBase()
        roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        user_base.roles = roles
        assert user_base.roles_raw[0]["role"] == "co2.superadmin"


class TestUserCalculatePermissions:
    """Tests for User.calculate_permissions method."""

    def test_calculate_permissions_empty_roles(self):
        """Test calculate_permissions with no roles."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
            roles=[],
        )
        perms = user.calculate_permissions()
        assert perms == {}

    def test_calculate_permissions_with_roles(self):
        """Test calculate_permissions with roles."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        # Set roles after creation to ensure setter is called
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        perms = user.calculate_permissions()
        assert "modules.professional_travel" in perms
        assert perms["modules.professional_travel"]["view"] is True
        assert perms["modules.professional_travel"]["edit"] is True


class TestUserHasRole:
    """Tests for User.has_role method (deprecated)."""

    def test_has_role_true(self):
        """Test has_role returns True when user has the role."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        # Set roles after creation to ensure setter is called
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        # Verify roles are set correctly
        assert len(user.roles) == 1
        assert user.roles[0].role == RoleName.CO2_USER_STD
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # Compare with enum value - RoleName is str, Enum so should compare
            # with string
            assert user.has_role(f"{RoleName.CO2_USER_STD.value}") is True

    def test_has_role_false(self):
        """Test has_role returns False when user doesn't have the role."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert user.has_role(f"{RoleName.CO2_USER_PRINCIPAL.value}") is False

    def test_has_role_empty_roles(self):
        """Test has_role with empty roles."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert user.has_role(f"{RoleName.CO2_USER_STD.value}") is False

    def test_has_role_deprecation_warning(self):
        """Test that has_role raises deprecation warning."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            user.has_role(f"{RoleName.CO2_USER_STD.value}")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)


class TestUserHasRoleOn:
    """Tests for User.has_role_on method (deprecated)."""

    def test_has_role_on_true(self):
        """Test has_role_on returns True when user has the role on the scope."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert (
                user.has_role_on(f"{RoleName.CO2_USER_STD.value}", "unit", "12345")
                is True
            )

    def test_has_role_on_false_wrong_unit(self):
        """Test has_role_on returns False for wrong unit."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert (
                user.has_role_on(f"{RoleName.CO2_USER_STD.value}", "unit", "99999")
                is False
            )

    def test_has_role_on_false_wrong_role(self):
        """Test has_role_on returns False for wrong role."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345"))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert (
                user.has_role_on(
                    f"{RoleName.CO2_USER_PRINCIPAL.value}", "unit", "12345"
                )
                is False
            )

    def test_has_role_on_with_affiliation(self):
        """Test has_role_on with affiliation scope."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=RoleScope(affiliation="TEST-AFF"),
            )
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert (
                user.has_role_on("co2.backoffice.metier", "affiliation", "TEST-AFF")
                is True
            )


class TestUserHasRoleGlobal:
    """Tests for User.has_role_global method (deprecated)."""

    def test_has_role_global_true(self):
        """Test has_role_global returns True when user has global role."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert user.has_role_global("co2.superadmin") is True

    def test_has_role_global_false_unit_scope(self):
        """Test has_role_global returns False for unit scope."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=RoleScope(unit="12345"))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert user.has_role_global("co2.superadmin") is False

    def test_has_role_global_false_wrong_role(self):
        """Test has_role_global returns False for wrong role."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert user.has_role_global("co2.superadmin") is False

    def test_has_role_global_empty_roles(self):
        """Test has_role_global with empty roles."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        user.roles = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert user.has_role_global("co2.superadmin") is False


class TestUserRepr:
    """Tests for User.__repr__ method."""

    def test_user_repr(self):
        """Test User string representation."""
        user = User(
            id="test-user",
            email="test@example.com",
            provider="test",
        )
        assert repr(user) == "<User test@example.com>"
