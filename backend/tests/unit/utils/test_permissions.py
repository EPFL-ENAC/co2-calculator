"""Unit tests for permission calculation utilities.

Tests cover:
- calculate_user_permissions with all role types
- has_permission helper function
- get_permission_value helper function
- Edge cases and combinations
"""

import pytest

from app.models.user import (
    AffiliationScope,
    GlobalScope,
    OwnScope,
    Role,
    RoleName,
    UnitScope,
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
        """Test superadmin with global scope grants every backoffice page."""
        roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert "view" in result["backoffice.users"]
        assert "edit" in result["backoffice.users"]
        assert "export" in result["backoffice.users"]
        assert "edit" in result["backoffice.configuration"]
        assert "view" in result["backoffice.logs"]
        assert "edit" in result["backoffice.pipeline_operations"]
        assert "edit" in result["backoffice.ui_texts"]
        assert "system.users" not in result
        assert "backoffice.data_management" not in result
        assert "modules.headcount" not in result
        assert "modules.equipment" not in result

    def test_backoffice_metier_global_scope_grants_nothing(self):
        """CO2_BACKOFFICE_METIER is sub-perimeter-bound: a GlobalScope shape is
        not produced by ACCRED and grants no permissions. Only CO2_SUPERADMIN
        gets cross-affiliation backoffice reach."""
        roles = [Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope())]
        result = calculate_user_permissions(roles)
        assert result == {}

    def test_superadmin_wrong_scope(self):
        """Test superadmin with unit scope does not grant permissions."""
        roles = [
            Role(
                role=RoleName.CO2_SUPERADMIN,
                on=UnitScope(institutional_id="10208"),
            )
        ]
        result = calculate_user_permissions(roles)

        assert "backoffice.users" not in result

    def test_user_principal_unit_scope(self):
        """Test user principal with unit scope grants module permissions."""
        roles = [
            Role(
                role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="10208")
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
        # Principal is a unit role only — no backoffice.* grants. Backoffice
        # access requires CO2_BACKOFFICE_METIER (or CO2_SUPERADMIN).
        assert not any(key.startswith("backoffice.") for key in result), (
            f"Principal leaked backoffice keys: "
            f"{[k for k in result if k.startswith('backoffice.')]}"
        )

    def test_user_std_unit_scope(self):
        """Test user std with unit scope grants view and edit for professional_travel."""  # noqa: E501
        roles = [
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="10208"))
        ]
        result = calculate_user_permissions(roles)

        # Standard user is own-scoped → ``modules.X/<unit>/own`` keys.
        assert "modules.headcount/10208/own" not in result
        assert "modules.equipment/10208/own" not in result
        assert "modules.professional_travel/10208/own" in result
        assert "view" in result["modules.professional_travel/10208/own"]
        assert "edit" in result["modules.professional_travel/10208/own"]
        assert "modules.buildings/10208/own" not in result
        assert "modules.purchase/10208/own" not in result
        assert "modules.research_facilities/10208/own" not in result
        assert "modules.external_cloud_and_ai/10208/own" in result
        assert "view" in result["modules.external_cloud_and_ai/10208/own"]
        assert "edit" in result["modules.external_cloud_and_ai/10208/own"]

    def test_user_roles_wrong_scope(self):
        """Test user roles with global scope do not grant permissions."""
        roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]
        result = calculate_user_permissions(roles)

        assert "modules.headcount/10208" not in result

    def test_combined_backoffice_and_user_roles(self):
        """Test that permissions from different domains combine.

        Uses the affiliation-scoped backoffice shape because that is the only
        valid CO2_BACKOFFICE_METIER configuration (GlobalScope is not produced
        by ACCRED for this role)."""
        roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=AffiliationScope(affiliation="SV"),
            ),
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="10208")),
        ]
        result = calculate_user_permissions(roles)

        # Backoffice: reporting is affiliation-scoped; users is scope-less (#862)
        assert "backoffice.reporting/SV" in result
        assert "view" in result["backoffice.reporting/SV"]
        assert "backoffice.users" in result
        assert "view" in result["backoffice.users"]

        # Std module grants are own-scoped (``/own``).
        assert "view" in result["modules.professional_travel/10208/own"]
        assert "edit" in result["modules.professional_travel/10208/own"]
        assert "modules.headcount/10208/own" not in result
        assert "modules.equipment/10208/own" not in result

    def test_multiple_user_roles_same_unit(self):
        """Test multiple user roles for same unit combine correctly."""
        roles = [
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id="10208")),
            Role(
                role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="10208")
            ),
        ]
        result = calculate_user_permissions(roles)

        # Principal grants are unit-scoped (no ``/own`` suffix).
        assert "view" in result["modules.headcount/10208"]
        assert "edit" in result["modules.headcount/10208"]
        assert "view" in result["modules.professional_travel/10208"]
        assert "edit" in result["modules.professional_travel/10208"]

    def test_role_name_as_string(self):
        """Test that role name can be string or enum."""
        # Create role with string role name
        role_dict = {
            "role": f"{RoleName.CO2_SUPERADMIN.value}",
            "on": {"kind": "global"},
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


class TestHasPermissionInstitutionalId:
    """Scoped lookup via the ``institutional_id`` kwarg."""

    def test_scoped_match(self):
        perms = {"modules.headcount/0184": ["view", "edit"]}
        assert (
            has_permission(perms, "modules.headcount", "view", institutional_id="0184")
            is True
        )

    def test_scoped_match_misses_unscoped_key(self):
        """A bare ``modules.headcount`` key must NOT satisfy a scoped check —
        scope must be enforced strictly when iid is provided."""
        perms = {"modules.headcount": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "view", institutional_id="0184")
            is False
        )

    def test_scoped_wrong_unit(self):
        perms = {"modules.headcount/0184": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "view", institutional_id="9999")
            is False
        )

    def test_scoped_action_missing(self):
        perms = {"modules.headcount/0184": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "edit", institutional_id="0184")
            is False
        )


class TestHasPermissionAnyScope:
    """Any-scope lookup. Taxonomy-only escape hatch."""

    def test_any_scope_matches_scoped_key(self):
        perms = {"modules.headcount/0184": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "view", any_scope=True) is True
        )

    def test_any_scope_matches_unscoped_key(self):
        perms = {"modules.headcount": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "view", any_scope=True) is True
        )

    def test_any_scope_no_match(self):
        perms = {"modules.equipment/0184": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "view", any_scope=True) is False
        )

    def test_any_scope_action_missing(self):
        perms = {"modules.headcount/0184": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "edit", any_scope=True) is False
        )

    def test_any_scope_does_not_leak_across_modules(self):
        """``modules.headcount/`` prefix must not match e.g.
        ``modules.headcount_x/...``"""
        perms = {"modules.headcount_x/0184": ["view"]}
        assert (
            has_permission(perms, "modules.headcount", "view", any_scope=True) is False
        )


# ─────────────────────────────────────────────────────────────────────────────
# Role-composition tests
#
# Three layers, each catching a different class of regression:
#   1. Domain isolation       — each role only emits keys in its own domain
#                               (modules.* / backoffice.* / system.*)
#   2. Composition matrix     — multi-role combinations produce the expected
#                               key-set with no scope leaks
#   3. Scope-leak invariants  — structural rules that must hold for ANY input
#
# Why this matters:
#   PR #974 changed module-permission keys to ``modules.X/{institutional_id}``.
#   The three role domains (user.*, backoffice.*, system.*) are independent
#   "apps" and must not collide. Module perms are scoped per unit; backoffice
#   and system perms are always un-scoped. These tests pin those rules.
# ─────────────────────────────────────────────────────────────────────────────

# Module sets each user-role grants. Kept as bare names so we can scope them
# per-unit at test time via ``_modules(names, iid)``.
_PRINCIPAL_MODULES = (
    "headcount",
    "equipment",
    "professional_travel",
    "buildings",
    "purchase",
    "research_facilities",
    "external_cloud_and_ai",
    "process_emissions",
)
_STD_MODULES = ("professional_travel", "external_cloud_and_ai")

_BACKOFFICE_AFF = "SV"
# Keys emitted by CO2_BACKOFFICE_METIER (#862): only reporting is
# affiliation-scoped; users/documentation/ui_texts are scope-less.
_BACKOFFICE_KEYS = frozenset(
    {
        f"backoffice.reporting/{_BACKOFFICE_AFF}",
        "backoffice.configuration",
        "backoffice.documentation",
        "backoffice.pipeline_operations",
        "backoffice.ui_texts",
    }
)
# Bare key shape emitted by CO2_SUPERADMIN (every backoffice page, global).
_BACKOFFICE_KEYS_BARE = frozenset(
    {
        "backoffice.reporting",
        "backoffice.users",
        "backoffice.documentation",
        "backoffice.ui_texts",
        "backoffice.configuration",
        "backoffice.pipeline_operations",
        "backoffice.logs",
    }
)
# Pages only CO2_SUPERADMIN gets (never metier / principal / std).
_SUPERADMIN_ONLY_KEYS = frozenset(
    {
        "backoffice.configuration",
        "backoffice.pipeline_operations",
        "backoffice.logs",
    }
)

_IID_A = "0184"
_IID_B = "9999"


def _modules(names, iid: str, *, own: bool = False) -> set[str]:
    """Build the scoped module-permission keys for a given unit.

    ``own=True`` appends the ``/own`` suffix emitted for standard users.
    """
    suffix = "/own" if own else ""
    return {f"modules.{n}/{iid}{suffix}" for n in names}


def _r_principal(iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id=iid))


def _r_std(iid: str) -> Role:
    return Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id=iid))


def _r_backoffice() -> Role:
    """Backoffice metier — always sub-perimeter-bound (affiliation-scoped).
    GlobalScope is not a valid configuration for this role."""
    return Role(
        role=RoleName.CO2_BACKOFFICE_METIER,
        on=AffiliationScope(affiliation=_BACKOFFICE_AFF),
    )


def _r_superadmin() -> Role:
    return Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())


class TestRoleDomainIsolation:
    """Layer 1: each role only emits keys in its declared domain.

    This is the structural firewall — if someone adds e.g. ``modules.X`` to
    backoffice or ``system.Y`` to a user role, this test fires immediately.
    """

    @pytest.mark.parametrize(
        "role, allowed_prefixes",
        [
            pytest.param(_r_std(_IID_A), ("modules.",), id="std"),
            pytest.param(
                _r_principal(_IID_A),
                # Principal is a unit-area role: only modules.* keys.
                # (backoffice.users.edit was removed in #459 Phase 2.)
                ("modules.",),
                id="principal",
            ),
            pytest.param(_r_backoffice(), ("backoffice.",), id="backoffice"),
            pytest.param(_r_superadmin(), ("backoffice.",), id="superadmin"),
        ],
    )
    def test_role_only_grants_keys_in_its_domain(self, role, allowed_prefixes):
        perms = calculate_user_permissions([role])
        for key in perms:
            assert any(key.startswith(p) for p in allowed_prefixes), (
                f"Role {role.role} produced out-of-domain key: {key!r} "
                f"(allowed prefixes: {allowed_prefixes})"
            )


# ── Composition matrix ───────────────────────────────────────────────────────
#
# Each row asserts:
#   - ``expected``  — keys that MUST be in the result
#   - ``forbidden`` — keys that MUST NOT be in the result
# Action sets are intentionally NOT checked here; Layer-1 + invariants below
# already cover the structural concerns, and the simpler matrix stays readable.

# Pre-built sets reused across rows
_PRINCIPAL_KEYS_A = _modules(_PRINCIPAL_MODULES, _IID_A)
_PRINCIPAL_KEYS_B = _modules(_PRINCIPAL_MODULES, _IID_B)
_STD_KEYS_A = _modules(_STD_MODULES, _IID_A, own=True)
_STD_KEYS_B = _modules(_STD_MODULES, _IID_B, own=True)


_COMPOSITION_CASES = [
    pytest.param(
        [_r_principal(_IID_A)],
        _PRINCIPAL_KEYS_A,
        _PRINCIPAL_KEYS_B | _BACKOFFICE_KEYS | _BACKOFFICE_KEYS_BARE,
        id="principal-A",
    ),
    pytest.param(
        [_r_std(_IID_A)],
        _STD_KEYS_A,
        (_PRINCIPAL_KEYS_A - _STD_KEYS_A) | _BACKOFFICE_KEYS | _BACKOFFICE_KEYS_BARE,
        id="std-A",
    ),
    pytest.param(
        # Backoffice metier: scoped reporting + scope-less users/docs/ui_texts;
        # never the super-admin-only pages or a bare reporting key.
        [_r_backoffice()],
        set(_BACKOFFICE_KEYS),
        _PRINCIPAL_KEYS_A | {"backoffice.reporting"},  # ADD BACK _SUPERADMIN_ONLY_KEYS
        id="backoffice",
    ),
    pytest.param(
        # Superadmin: every backoffice page bare (global); never scoped reporting.
        [_r_superadmin()],
        set(_BACKOFFICE_KEYS_BARE),
        _PRINCIPAL_KEYS_A | {f"backoffice.reporting/{_BACKOFFICE_AFF}"},
        id="superadmin",
    ),
    pytest.param(
        # std + principal on the same unit: principal subsumes std (idempotent).
        [_r_std(_IID_A), _r_principal(_IID_A)],
        _PRINCIPAL_KEYS_A,
        _PRINCIPAL_KEYS_B | _BACKOFFICE_KEYS | _BACKOFFICE_KEYS_BARE,
        id="std+principal-same-unit",
    ),
    pytest.param(
        # Multi-unit: full perms on A, only travel+cloud on B. Critically,
        # principal-only modules MUST NOT appear under /B.
        [_r_principal(_IID_A), _r_std(_IID_B)],
        _PRINCIPAL_KEYS_A | _STD_KEYS_B,
        (_PRINCIPAL_KEYS_B - _STD_KEYS_B) | _BACKOFFICE_KEYS | _BACKOFFICE_KEYS_BARE,
        id="principal-A+std-B",
    ),
    pytest.param(
        # backoffice + principal — super-admin-only pages must stay absent.
        [_r_backoffice(), _r_principal(_IID_A)],
        _PRINCIPAL_KEYS_A | _BACKOFFICE_KEYS,
        {"backoffice.reporting"},  # add back _SUPERADMIN_ONLY_KEYS
        id="backoffice+principal",
    ),
    pytest.param(
        # All roles — full union, nothing forbidden. Metier adds scoped
        # reporting; superadmin adds the bare keys (incl. bare reporting).
        [_r_superadmin(), _r_backoffice(), _r_principal(_IID_A)],
        _PRINCIPAL_KEYS_A | _BACKOFFICE_KEYS | _BACKOFFICE_KEYS_BARE,
        set(),
        id="superadmin+backoffice+principal",
    ),
]


class TestRoleCompositionKeys:
    """Layer 2: role combinations produce the expected key-set."""

    @pytest.mark.parametrize("roles, expected, forbidden", _COMPOSITION_CASES)
    def test_composition(self, roles, expected, forbidden):
        perms = calculate_user_permissions(roles)
        keys = set(perms)

        missing = expected - keys
        assert not missing, f"missing expected keys: {sorted(missing)}"

        leaked = forbidden & keys
        assert not leaked, f"unexpected keys present: {sorted(leaked)}"


# Representative role lists used by the invariant checks below
_INVARIANT_ROLE_LISTS = [
    [_r_std(_IID_A)],
    [_r_principal(_IID_A)],
    [_r_backoffice()],
    [_r_superadmin()],
    [_r_std(_IID_A), _r_principal(_IID_A)],
    [_r_principal(_IID_A), _r_std(_IID_B)],
    [_r_backoffice(), _r_principal(_IID_A)],
    [_r_superadmin(), _r_backoffice(), _r_principal(_IID_A)],
]


class TestPermissionInvariants:
    """Layer 3: structural rules that must hold for ANY role input."""

    @pytest.mark.parametrize("roles", _INVARIANT_ROLE_LISTS)
    def test_no_module_key_is_unscoped(self, roles):
        """Every ``modules.*`` key must carry an ``/{institutional_id}`` suffix.
        A bare ``modules.X`` key would mean the scope-blind regression that
        PR #974 was designed to close."""
        perms = calculate_user_permissions(roles)
        for key in perms:
            if key.startswith("modules."):
                assert "/" in key, (
                    f"Un-scoped module key found: {key!r} (roles={roles})"
                )

    @pytest.mark.parametrize("roles", _INVARIANT_ROLE_LISTS)
    def test_system_keys_never_scoped(self, roles):
        """``system.*`` permissions are flat — adding a unit suffix would
        silently break un-scoped lookups. (``backoffice.*`` is scoped by
        affiliation for sub-perimeter managers since #459; see the dedicated
        backoffice tests below.)"""
        perms = calculate_user_permissions(roles)
        for key in perms:
            if key.startswith("system."):
                assert "/" not in key, (
                    f"Scoped system key found: {key!r} (roles={roles})"
                )

    @pytest.mark.parametrize("roles", _INVARIANT_ROLE_LISTS)
    def test_backoffice_keys_only_scoped_by_affiliation(self, roles):
        """Backoffice keys are either bare (GlobalScope / superadmin / principal
        side-grant) or carry an affiliation suffix ``/<aff>`` (#459). A unit-id
        suffix on a backoffice key would mean a wrongly-shaped scope leaked
        through ``as_scope_key``."""
        perms = calculate_user_permissions(roles)
        for key in perms:
            if not key.startswith("backoffice."):
                continue
            if "/" not in key:
                continue
            suffix = key.split("/", 1)[1]
            # Affiliations are name-like tokens (e.g. "SV", "Engineering") —
            # never the all-digit institutional_id shape ("0184", "10208").
            assert not suffix.isdigit(), (
                f"Backoffice key carries unit-id suffix: {key!r} (roles={roles})"
            )

    def test_principal_subsumes_std_for_same_unit(self):
        """``[std, principal]`` for the same unit keeps every principal
        (unit-breadth) key with at least the same actions. The std role adds
        its own-scoped (``/own``) keys, which are functionally redundant with
        the unit-breadth grant but coexist as distinct keys (#role-scope)."""
        principal_only = calculate_user_permissions([_r_principal(_IID_A)])
        combined = calculate_user_permissions([_r_std(_IID_A), _r_principal(_IID_A)])
        assert set(principal_only) <= set(combined)
        for key, actions in principal_only.items():
            assert set(combined[key]) >= set(actions), (
                f"principal lost actions on {key} when merged with std: "
                f"{set(actions) - set(combined[key])}"
            )
        # The only extra keys are std's own-scoped grants.
        assert (set(combined) - set(principal_only)) <= _STD_KEYS_A

    def test_cross_unit_no_principal_leak(self):
        """A user with ``principal/A`` and ``std/B`` must not get
        principal-only modules on unit B."""
        perms = calculate_user_permissions([_r_principal(_IID_A), _r_std(_IID_B)])
        principal_only = set(_PRINCIPAL_MODULES) - set(_STD_MODULES)
        for module in principal_only:
            assert f"modules.{module}/{_IID_B}" not in perms, (
                f"Cross-unit leak: {module} appeared under unit B"
            )


class TestBackofficeAffiliationScoping:
    """Backoffice sub-perimeter scoping by ACCRED affiliation (#459).

    Affiliation-scoped backoffice users hold ``backoffice.X/<affiliation>``
    keys; GlobalScope users keep the bare ``backoffice.X`` keys. The two
    shapes coexist via the ``any_scope=True`` lookup mode on endpoints.
    """

    # Bare keys CO2_SUPERADMIN holds (every backoffice page, global).
    _BACKOFFICE_BARE = (
        "backoffice.reporting",
        "backoffice.users",
        "backoffice.documentation",
        "backoffice.ui_texts",
        "backoffice.configuration",
        "backoffice.pipeline_operations",
        "backoffice.logs",
    )

    def test_affiliation_scope_emits_expected_keys(self):
        """An SV-scoped metier user holds scoped reporting + scope-less
        users/documentation/ui_texts only (#862). Reporting is the sole
        affiliation-scoped area; the super-admin pages are absent."""
        roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=AffiliationScope(affiliation="SV"),
            )
        ]
        perms = calculate_user_permissions(roles)
        assert set(perms) == {
            "backoffice.reporting/SV",
            "backoffice.users",
            "backoffice.configuration",
            "backoffice.pipeline_operations",
            "backoffice.documentation",
            "backoffice.ui_texts",
        }
        assert set(perms["backoffice.reporting/SV"]) == {"view", "export"}
        assert set(perms["backoffice.users"]) == {"view", "edit", "export"}
        assert set(perms["backoffice.documentation"]) == {"view", "edit"}
        assert set(perms["backoffice.ui_texts"]) == {"view", "edit"}

    def test_scoped_backoffice_lacks_superadmin_pages(self):
        """Regression pin: metier MUST NOT hold the super-admin-only pages
        (configuration / pipeline_operations / logs) nor any data_management
        key. Granting those would let a non-Super-Admin trigger syncs or mutate
        factor data."""
        roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=AffiliationScope(affiliation="SV"),
            )
        ]
        perms = calculate_user_permissions(roles)
        for key in (
            # "backoffice.configuration",
            # "backoffice.pipeline_operations", # TODO add back when permission change
            "backoffice.logs",
        ):
            assert key not in perms
        assert not any(k.startswith("backoffice.data_management") for k in perms)

    def test_superadmin_has_configuration_pipeline_logs(self):
        """Counterpart: Super Admin holds the page-driven super-admin keys and
        no longer the removed system.users / data_management keys."""
        roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        perms = calculate_user_permissions(roles)
        assert set(perms["backoffice.configuration"]) == {"view", "edit"}
        assert set(perms["backoffice.pipeline_operations"]) == {"view", "edit"}
        assert set(perms["backoffice.logs"]) == {"view"}
        assert "backoffice.data_management" not in perms
        assert "system.users" not in perms

    def test_superadmin_keeps_bare_keys(self):
        """CO2_SUPERADMIN emits bare backoffice.* keys (no ``/<aff>`` suffix)
        for every page. CO2_BACKOFFICE_METIER cannot reach this shape."""
        roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        perms = calculate_user_permissions(roles)
        for path in self._BACKOFFICE_BARE:
            assert path in perms, f"missing bare key {path}"
            assert f"{path}/" not in " ".join(perms), (
                f"Superadmin leaked a scoped variant of {path}"
            )

    def test_backoffice_metier_global_scope_grants_nothing(self):
        """Regression guard: CO2_BACKOFFICE_METIER + GlobalScope is an
        unconfigured shape (never produced by ACCRED) and yields no permissions."""
        roles = [Role(role=RoleName.CO2_BACKOFFICE_METIER, on=GlobalScope())]
        assert calculate_user_permissions(roles) == {}

    def test_multi_affiliation_unions(self):
        """Two metier roles on SV and STI → both scoped reporting keys present;
        the bare reporting key never appears (users stays scope-less)."""
        roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=AffiliationScope(affiliation="SV"),
            ),
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=AffiliationScope(affiliation="STI"),
            ),
        ]
        perms = calculate_user_permissions(roles)
        assert "backoffice.reporting/SV" in perms
        assert "backoffice.reporting/STI" in perms
        assert "backoffice.reporting" not in perms
        # users is scope-less even for metier
        assert "backoffice.users" in perms

    def test_affiliation_scope_via_dict_role(self):
        """Roles deserialized from JSON come in as dicts — the dict branch of
        ``as_scope_key`` must produce the same ``/<affiliation>`` suffix on the
        scoped reporting key."""
        role_dict = {
            "role": RoleName.CO2_BACKOFFICE_METIER.value,
            "on": {"kind": "affiliation", "affiliation": "SV"},
        }
        perms = calculate_user_permissions([Role(**role_dict)])
        assert "backoffice.reporting/SV" in perms

    def test_iid_role_scope_grants_nothing(self):
        """Defensive: ACCRED never produces an institutional_id-scoped backoffice
        role. Such a shape is not affiliation-scoped, so it grants nothing rather
        than emitting a meaningless ``backoffice.reporting/0184``."""
        roles = [
            Role(
                role=RoleName.CO2_BACKOFFICE_METIER,
                on=UnitScope(institutional_id="0184"),
            )
        ]
        assert calculate_user_permissions(roles) == {}


class TestHasPermissionAnyScopeAffiliation:
    """``has_permission(..., any_scope=True)`` must match affiliation keys.

    This pins the rationale for swapping ``require_permission`` for an inline
    ``any_scope=True`` check on the backoffice endpoints (#459).
    """

    def test_any_scope_matches_affiliation_key(self):
        perms = {"backoffice.users/SV": ["view", "edit", "export"]}
        assert has_permission(perms, "backoffice.users", "view", any_scope=True) is True

    def test_default_lookup_misses_affiliation_key(self):
        """A bare-path lookup against an affiliation-only user must return
        False — this is exactly why the endpoints need ``any_scope=True``."""
        perms = {"backoffice.users/SV": ["view"]}
        assert has_permission(perms, "backoffice.users", "view") is False


class TestHasPermissionAgainstRealPermissions:
    """Bridge tests: feed ``has_permission`` the actual output of
    ``calculate_user_permissions``. If the two sides ever disagree on the key
    format (e.g. someone changes the ``/`` separator on one side), these fail.
    """

    def test_principal_scoped_lookup_matches(self):
        perms = calculate_user_permissions([_r_principal(_IID_A)])
        # Right unit → granted
        for module in _PRINCIPAL_MODULES:
            assert has_permission(
                perms, f"modules.{module}", "view", institutional_id=_IID_A
            ), f"principal/A should have view on modules.{module}"
        # Wrong unit → denied
        for module in _PRINCIPAL_MODULES:
            assert not has_permission(
                perms, f"modules.{module}", "view", institutional_id=_IID_B
            ), f"principal/A must NOT have view on modules.{module}/{_IID_B}"
        # Bare-path lookup → denied (no global module key was emitted)
        assert not has_permission(perms, "modules.headcount", "view")

    def test_std_scoped_lookup_only_matches_std_modules(self):
        perms = calculate_user_permissions([_r_std(_IID_A)])
        # Std grants only travel + cloud_and_ai
        for module in _STD_MODULES:
            assert has_permission(
                perms, f"modules.{module}", "view", institutional_id=_IID_A
            ), f"std/A should have view on modules.{module}"
        # Modules std doesn't grant → denied
        for module in set(_PRINCIPAL_MODULES) - set(_STD_MODULES):
            assert not has_permission(
                perms, f"modules.{module}", "view", institutional_id=_IID_A
            ), f"std/A must NOT have view on modules.{module}"

    def test_any_scope_taxonomy_lookup_matches_principal(self):
        """Taxonomy endpoints use ``any_scope=True``. A principal on any unit
        should pass the module-level taxonomy gate."""
        perms = calculate_user_permissions([_r_principal(_IID_A)])
        for module in _PRINCIPAL_MODULES:
            assert has_permission(perms, f"modules.{module}", "view", any_scope=True), (
                f"taxonomy gate failed for {module}"
            )


class TestMultiUnitSameRole:
    """Same role across multiple units must compose without dominating either."""

    def test_principal_on_two_units(self):
        perms = calculate_user_permissions([_r_principal(_IID_A), _r_principal(_IID_B)])
        keys = set(perms)
        for module in _PRINCIPAL_MODULES:
            assert f"modules.{module}/{_IID_A}" in keys
            assert f"modules.{module}/{_IID_B}" in keys

    def test_std_on_two_units(self):
        perms = calculate_user_permissions([_r_std(_IID_A), _r_std(_IID_B)])
        keys = set(perms)
        for module in _STD_MODULES:
            assert f"modules.{module}/{_IID_A}/own" in keys
            assert f"modules.{module}/{_IID_B}/own" in keys
        # Modules std doesn't grant must be absent on both units
        for module in set(_PRINCIPAL_MODULES) - set(_STD_MODULES):
            assert f"modules.{module}/{_IID_A}/own" not in keys
            assert f"modules.{module}/{_IID_B}/own" not in keys
