"""Coherence tests for the TEST provider fixtures.

The backoffice_metier scope token is a unit cf (``institutional_id``). The
reporting query resolves it to descendant units via the indexed
``path_institutional_code`` (cf -> institutional_code -> path token match).
These tests assert TEST fixtures are hierarchically coherent under that rule,
so end-to-end backoffice tests exercise a real subtree rather than an empty one.
"""

from app.models.user import AffiliationScope, RoleName
from app.providers.test_fixtures import (
    TEST_AFFILIATION,
    TEST_ROLES,
    TEST_UNITS,
)


def test_backoffice_metier_scope_is_a_unit_cf():
    """TEST_AFFILIATION must equal the cf of a TEST unit (the scope anchor)."""
    anchor = next(
        (u for u in TEST_UNITS if u.institutional_id == TEST_AFFILIATION), None
    )
    assert anchor is not None, (
        "TEST_AFFILIATION must be the institutional_id (cf) of a TEST unit; "
        f"got {TEST_AFFILIATION!r}"
    )


def test_scope_anchor_resolves_to_descendant_units():
    """cf -> institutional_code -> path_institutional_code must match >=1 unit.

    Mirrors the reporting scope resolver: the anchor's institutional_code must
    appear as a path token in its own and its descendants' path, since
    path_institutional_code is self-inclusive (" ".join(ancestors + [self])).
    """
    anchor = next(u for u in TEST_UNITS if u.institutional_id == TEST_AFFILIATION)
    code = anchor.institutional_code

    in_subtree = [
        u for u in TEST_UNITS if code in (u.path_institutional_code or "").split()
    ]
    assert in_subtree, (
        "anchor institutional_code must appear in descendant "
        "path_institutional_code tokens"
    )
    assert anchor in in_subtree, "path_institutional_code must be self-inclusive"


def test_backoffice_metier_role_scope_matches_affiliation_constant():
    """The metier role's AffiliationScope must carry TEST_AFFILIATION."""
    roles = TEST_ROLES[RoleName.CO2_BACKOFFICE_METIER]
    scopes = [r.on for r in roles if isinstance(r.on, AffiliationScope)]
    assert any(s.affiliation == TEST_AFFILIATION for s in scopes)
