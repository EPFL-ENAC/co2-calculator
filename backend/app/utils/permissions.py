"""Permission calculation utilities.

This module provides functions to calculate user permissions based on their roles.
Permissions are calculated dynamically from roles and returned as a structured dict.
"""

from typing import Optional


def derive_backoffice_affiliations(
    permissions: Optional[dict],
    anchor_path: str = "backoffice.users",
) -> tuple[bool, set[str]]:
    """Inspect permission keys for backoffice sub-perimeter scoping (#459).

    Returns ``(is_global, affiliations)``:
    - ``is_global`` is True iff the bare ``anchor_path`` key is present, meaning
      the user holds a ``GlobalScope`` (or superadmin) backoffice grant and
      should NOT be narrowed.
    - ``affiliations`` is the set of sub-perimeter labels parsed from
      ``{anchor_path}/<aff>`` keys (multi-affiliation users yield multiple
      entries — natural union semantics).

    ``backoffice.users`` is the canonical anchor because all four backoffice
    permission groups are emitted in lockstep by ``calculate_user_permissions``
    for ``CO2_BACKOFFICE_METIER``.
    """
    if not permissions:
        return False, set()
    is_global = anchor_path in permissions
    prefix = f"{anchor_path}/"
    affiliations = {k.removeprefix(prefix) for k in permissions if k.startswith(prefix)}
    return is_global, affiliations


def has_permission(
    permissions: Optional[dict],
    path: str,
    action: str = "view",
    *,
    institutional_id: Optional[str] = None,
    any_scope: bool = False,
) -> bool:
    """Check if a permission exists and grants ``action``.

    Permission keys may be un-scoped (``"backoffice.users"``, ``"system.users"``)
    or scoped to a unit (``"modules.headcount/0184"``). Only ``modules.*`` permissions
    are unit-scoped — ``backoffice.*`` and ``system.*`` permissions are always stored
    un-scoped. Callers pick the matching mode via kwargs:

    - ``institutional_id`` set: strict match on ``f"{path}/{institutional_id}"``.
      Use this when the caller has a unit context (route handlers gating a unit-scoped
      module action).
    - Neither kwarg: strict match on the bare ``path``. This is the right default
      for un-scoped permissions (``backoffice.*``, ``system.*``).
    - ``any_scope=True``: bare path OR any ``f"{path}/*"`` key.

      EXCEPTION — only taxonomy endpoints (``app/api/v1/taxonomies.py``) should
      use this. Taxonomies expose module-level reference data (the list of valid
      data-entry types for a module) and are inherently scope-blind: we have no
      unit_id at call time. A user authorised on ANY unit for ``modules.X`` may
      legitimately read the ``X`` taxonomy. Do not use ``any_scope`` for routes
      that operate on unit data — it re-creates the scope-blind permission gap
      that PR #974 was specifically designed to close.

    Args:
        permissions: Permissions dict (from ``user.calculate_permissions()``).
        path: Base permission path (e.g. ``"modules.headcount"``).
        action: Action to check (default ``"view"``).
        institutional_id: Unit institutional_id for scoped lookup.
        any_scope: If True and ``institutional_id`` is None, also match any scoped
            variant of ``path``.

    Returns:
        True iff the action is granted under one of the candidate keys.
    """
    if not permissions:
        return False

    candidates: list[str]
    if institutional_id is not None:
        candidates = [f"{path}/{institutional_id}"]
    elif any_scope:
        scope_prefix = f"{path}/"
        candidates = [path, *[k for k in permissions if k.startswith(scope_prefix)]]
    else:
        candidates = [path]

    for key in candidates:
        actions = permissions.get(key)
        if isinstance(actions, list) and action in actions:
            return True
    return False
