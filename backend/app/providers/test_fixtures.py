"""Centralized test data for the TEST provider.

Single source of truth for test users, units, roles, and their relationships.
Used by TestRoleProvider, TestUnitProvider, and seed_fake_user_unit.
"""

import hashlib
from typing import Dict, List

from app.models.unit import Unit
from app.models.user import GlobalScope, Role, RoleName, RoleScope, UserProvider

TEST_AFFILIATION = "testaffiliation"


def make_test_user_id(user_id: str) -> str:
    """Make a consistent 10-digit numeric hash prefixed with TEST-.

    This is used to generate institutional_id for test users, ensuring that the same
    user_id string always maps to the same institutional_id. The TEST- prefix prevents
    collisions with real institutional IDs (e.g., EPFL IDs like "111756").
    """
    return "TEST-" + str(int(hashlib.sha256(user_id.encode()).hexdigest(), 16))[:10]


# -- Test Users ---------------------------------------------------------------
# Each entry keyed by the RoleName it represents.
# institutional_id is computed via make_test_user_id for consistency
# with the login-test flow.

TEST_USERS: Dict[RoleName, Dict[str, str]] = {
    RoleName.CO2_USER_STD: {
        "institutional_id": make_test_user_id("testuser_calco2.user.standard"),
        "email": "testuser_calco2.user.standard@example.org",
        "display_name": "Test User Standard",
        "function": "Tester",
    },
    RoleName.CO2_USER_PRINCIPAL: {
        "institutional_id": make_test_user_id("testuser_calco2.user.principal"),
        "email": "testuser_calco2.user.principal@example.org",
        "display_name": "Test User Principal",
        "function": "Tester",
    },
    RoleName.CO2_BACKOFFICE_METIER: {
        "institutional_id": make_test_user_id("testuser_calco2.backoffice.metier"),
        "email": "testuser_calco2.backoffice.metier@example.org",
        "display_name": "Test User Backoffice",
        "function": "Tester",
    },
    RoleName.CO2_SUPERADMIN: {
        "institutional_id": make_test_user_id("testuser_calco2.superadmin"),
        "email": "testuser_calco2.superadmin@example.org",
        "display_name": "Test User Superadmin",
        "function": "Tester",
    },
}

# Reverse lookup: institutional_id → RoleName
_USER_ID_TO_ROLE: Dict[str, RoleName] = {
    u["institutional_id"]: role for role, u in TEST_USERS.items()
}


def get_test_role_by_user_id(user_id: str) -> RoleName | None:
    """Resolve a test user institutional_id back to its RoleName."""
    return _USER_ID_TO_ROLE.get(user_id)


# -- Test Units ---------------------------------------------------------------
# principal_user_institutional_id uses the principal user's computed hash ID.

_PRINCIPAL_ID = TEST_USERS[RoleName.CO2_USER_PRINCIPAL]["institutional_id"]

TEST_UNITS: List[Unit] = [
    Unit(
        provider=UserProvider.TEST,
        institutional_code="TEST-12345",
        institutional_id="TEST-1119",
        name="ENAC-IT4R-TEST",
        level=4,
        principal_user_institutional_id=_PRINCIPAL_ID,
        path_institutional_code="10582 10583 11435",
        path_institutional_id="cf-10582 cf-10583 cf-11435",
        path_name="EPFL ENAC IT4R-TEST",
    ),
    Unit(
        provider=UserProvider.TEST,
        institutional_code="TEST-10208",
        institutional_id="TEST-0184",
        name="IC-TEST",
        level=3,
        principal_user_institutional_id=_PRINCIPAL_ID,
        path_institutional_code="10582 10583 11436",
        path_institutional_id="cf-10582 cf-10583 cf-11436",
        path_name="EPFL IC-TEST",
    ),
]

# Quick lookup helpers
TEST_UNIT_IDS = [u.institutional_id for u in TEST_UNITS if u.institutional_id]


# -- Test Roles ---------------------------------------------------------------
# Maps each RoleName to the list of Role objects assigned during test login.

TEST_ROLES: Dict[RoleName, List[Role]] = {
    RoleName.CO2_USER_STD: [
        Role(
            role=RoleName.CO2_USER_STD,
            on=RoleScope(
                institutional_id=TEST_UNITS[0].institutional_id,
                affiliation=TEST_AFFILIATION,
            ),
        ),
    ],
    RoleName.CO2_USER_PRINCIPAL: [
        Role(
            role=RoleName.CO2_USER_PRINCIPAL,
            on=RoleScope(
                institutional_id=TEST_UNITS[0].institutional_id,
                affiliation=TEST_AFFILIATION,
            ),
        ),
    ],
    RoleName.CO2_BACKOFFICE_METIER: [
        Role(
            role=RoleName.CO2_BACKOFFICE_METIER,
            on=RoleScope(affiliation=TEST_AFFILIATION),
        ),
    ],
    RoleName.CO2_SUPERADMIN: [
        Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope(scope="global")),
    ],
}
