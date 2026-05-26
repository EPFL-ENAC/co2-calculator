"""Affiliation-scoping helpers shared by backoffice routers (#459).

The pure permission utilities live in ``app.utils.permissions`` and stay
free of SQLAlchemy / FastAPI. This module owns the SQL-level predicate
that maps ACCRED affiliation tokens onto ``Unit.path_name``, plus the
gate helper that raises 403 when the caller is not a backoffice user.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col

from app.core.security import get_current_active_user
from app.models.unit import Unit
from app.models.user import User
from app.utils.permissions import derive_backoffice_affiliations, has_permission


def build_affiliation_predicate(affiliations: set[str]) -> ColumnElement[bool]:
    """Build the SQL predicate matching ``Unit.path_name`` against affiliations.

    ACCRED ``sortpath`` is a space-separated 4-level hierarchy
    (e.g. ``"EPFL ENAC ENAC-SG ENAC-IT"``); ``role_provider.py`` extracts
    LVL3 (``"ENAC-SG"``) as the affiliation token. ``Unit.path_name`` is a
    separator-joined ancestor list (observed shapes: ``"EPFL > STI > LMSC"``
    and ``"EPFL ENAC IT4R-TEST"``). Padding the column with leading/trailing
    spaces lets a single ``% <aff> %`` ILIKE catch the LVL3 token at any
    position regardless of separator (` > ` or plain space) and avoids false
    positives like ``SV`` matching ``SVOPS``.

    ``coalesce`` keeps the predicate well-defined when ``path_name`` is NULL
    (NULL rows simply never match).
    """
    padded = func.concat(" ", func.coalesce(col(Unit.path_name), ""), " ")
    return or_(*[padded.ilike(f"% {aff} %") for aff in affiliations])


def gate_backoffice(
    user: User,
    action: str = "view",
    anchor_path: str = "backoffice.users",
) -> tuple[bool, set[str]]:
    """Authorize ``<anchor_path>:<action>`` under any scope; return scope.

    Raises 403 if the user holds neither the bare ``anchor_path`` key nor any
    ``anchor_path/<aff>`` key granting ``action``. Returns
    ``(is_global, affiliations)``; callers apply ``build_affiliation_predicate``
    when ``is_global`` is False.

    The default anchor is ``backoffice.users`` (canonical for backoffice
    routes); pass ``backoffice.data_management`` for sync/pipeline routes
    or ``system.users`` for superadmin-only routes.

    Uses ``has_permission(..., any_scope=True)`` because affiliation-scoped
    users only hold ``<anchor>/<aff>`` keys — ``require_permission``'s
    literal-path lookup would 403 them.
    """
    perms = user.calculate_permissions()
    if not has_permission(perms, anchor_path, action, any_scope=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return derive_backoffice_affiliations(perms, anchor_path=anchor_path)


def require_any_scope(action: str = "view", anchor_path: str = "backoffice.users"):
    """FastAPI dependency factory: gate ``<anchor_path>:<action>`` any-scope.

    Drop-in replacement for ``require_permission`` for routes that only need
    the 403 gate, not the ``(is_global, affiliations)`` tuple. For routes
    that filter data by affiliation, call ``gate_backoffice`` inside the
    handler instead.

    Example::

        @router.get("/jobs")
        async def list_jobs(
            current_user: User = Depends(
                require_any_scope("view", "backoffice.data_management")
            ),
            ...
        ):
    """

    async def _dep(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        gate_backoffice(current_user, action=action, anchor_path=anchor_path)
        return current_user

    return _dep


def narrow_path_affiliation(
    requested: list[str] | None,
    is_global: bool,
    affiliations: set[str],
) -> list[str] | None:
    """Intersect a caller-provided ``path_affiliation`` filter with their scope.

    - ``is_global`` callers pass through unchanged.
    - Scoped callers: intersect their request with their affiliation set
      (or default to the full set when they pass nothing).
    - Returns the narrowed list; an empty list signals "no allowed affiliations"
      and the caller should short-circuit to an empty result.
    """
    if is_global:
        return requested
    if requested:
        return [a for a in requested if a in affiliations]
    return list(affiliations)
