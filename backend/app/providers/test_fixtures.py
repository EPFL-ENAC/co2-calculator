"""Centralized test data for the TEST provider.

Single source of truth for test users, units, roles, and their relationships.
Used by TestRoleProvider, TestUnitProvider, and seed_fake_user_unit.
"""

import hashlib
from typing import Dict, List

from app.models.unit import Unit
from app.models.user import (
    AffiliationScope,
    GlobalScope,
    OwnScope,
    Role,
    RoleName,
    UnitScope,
    UserProvider,
)

# Backoffice_metier scope token: the cf (institutional_id) of the ENAC anchor
# unit below. ACCRED grants the metier role on a unit at any level; scoping
# resolves that cf to the unit's descendant subtree.
TEST_AFFILIATION = "13030"


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
        "institutional_id": make_test_user_id("testuser_calco2.backoffice.admin"),
        "email": "testuser_calco2.backoffice.admin@example.org",
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

# A coherent ENAC subtree: lvl2 anchor -> lvl3 -> lvl4. Each unit's own
# institutional_code is the last token of its (self-inclusive) root->leaf
# path_institutional_code, mirroring real ACCRED data
# (" ".join(ancestors + [self])). EPFL root (code 10582 / cf 13029) is an
# ancestor token only; it is not a stored unit.
TEST_UNITS: List[Unit] = [
    Unit(
        provider=UserProvider.TEST,
        institutional_code="12635",
        institutional_id="13030",
        name="ENAC-TEST",
        level=2,
        principal_user_institutional_id=_PRINCIPAL_ID,
        path_institutional_code="10582 12635",
        path_institutional_id="13029 13030",
        path_name="EPFL ENAC-TEST",
    ),
    Unit(
        provider=UserProvider.TEST,
        institutional_code="11435",
        institutional_id="13031",
        name="ENAC-SG-TEST",
        level=3,
        principal_user_institutional_id=_PRINCIPAL_ID,
        path_institutional_code="10582 12635 11435",
        path_institutional_id="13029 13030 13031",
        path_name="EPFL ENAC-TEST ENAC-SG-TEST",
    ),
    Unit(
        provider=UserProvider.TEST,
        institutional_code="14270",
        institutional_id="13032",
        name="ENAC-IT4R-TEST",
        level=4,
        principal_user_institutional_id=_PRINCIPAL_ID,
        path_institutional_code="10582 12635 11435 14270",
        path_institutional_id="13029 13030 13031 13032",
        path_name="EPFL ENAC-TEST ENAC-SG-TEST ENAC-IT4R-TEST",
    ),
]

# Quick lookup helpers
TEST_UNIT_IDS = [u.institutional_id for u in TEST_UNITS if u.institutional_id]
# Primary (leaf) test unit id as a non-optional str for unit/own scope construction.
_TEST_UNIT_IID: str = TEST_UNITS[-1].institutional_id or ""


# -- Test Roles ---------------------------------------------------------------
# Maps each RoleName to the list of Role objects assigned during test login.

TEST_ROLES: Dict[RoleName, List[Role]] = {
    RoleName.CO2_USER_STD: [
        Role(
            role=RoleName.CO2_USER_STD,
            on=OwnScope(institutional_id=_TEST_UNIT_IID),
        ),
    ],
    RoleName.CO2_USER_PRINCIPAL: [
        Role(
            role=RoleName.CO2_USER_PRINCIPAL,
            on=UnitScope(institutional_id=_TEST_UNIT_IID),
        ),
    ],
    RoleName.CO2_BACKOFFICE_METIER: [
        Role(
            role=RoleName.CO2_BACKOFFICE_METIER,
            on=AffiliationScope(affiliation=TEST_AFFILIATION),
        ),
    ],
    RoleName.CO2_SUPERADMIN: [
        Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope()),
    ],
}
